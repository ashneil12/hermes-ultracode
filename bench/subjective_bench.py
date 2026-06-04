"""Run the DeepSeek solvers on the SUBJECTIVE bank: single-shot vs ultracode (judge-panel).

ultracode for generation = the judge-panel shape (N candidates from distinct angles/personas →
score with independent judges → synthesize the winner, grafting the best of the runners-up). This
is exactly the "exploration + taste" regime where a single first draft should lose to explore-and-
select. We save each output AND the process trace (mode, candidate count, winning angle) so the
benchmark grades the PROCESS too, not just the final text.

  python bench/subjective_bench.py single    deepseek-v4-flash
  python bench/subjective_bench.py ultracode  deepseek-v4-flash
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from bench.deepseek_client import DeepSeekClient
from bench.subjective_tasks import SUBJECTIVE_TASKS

RES = Path(__file__).resolve().parent / "results"


def _prompt(t):
    c = f"\n\nHARD CONSTRAINTS (must satisfy): {t.constraints}" if t.constraints else ""
    return f"{t.brief}{c}\n\nProduce ONLY the final piece (no preamble, no explanation)."


def run_single(model, tasks, workers=8):
    def one(t):
        cb = DeepSeekClient(model=model, max_workers=2)
        o = cb.chat([{"role": "system", "content": "You are an expert writer. Produce the single best piece for the brief."},
                     {"role": "user", "content": _prompt(t)}], temperature=0.7, max_tokens=1200)
        return {"output": type(cb)._content(o), "mode": "single"}
    return _fan(tasks, one, workers, "SINGLE")


def run_ultracode(model, tasks, workers=4):
    cfg = UltracodeConfig(concurrency=8, max_children=6, max_finders=5)
    def one(t):
        cu = DeepSeekClient(model=model, max_workers=10)
        res = run(_prompt(t), kind="generative", force_orchestrate=True, delegate_fn=cu.delegate_fn,
                  aux_call_fn=cu.aux_call_fn, config=cfg, enable_ledger=False, run_id=t.id)
        return {"output": res.answer, "mode": res.mode, "caps": res.caps_announced,
                "tokens": cu.usage.snapshot()["total_tokens"]}
    return _fan(tasks, one, workers, "ULTRA")


def _fan(tasks, fn, workers, label):
    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, t): t for t in tasks}
        for f in as_completed(futs):
            t = futs[f]
            try:
                out[t.id] = f.result()
            except Exception as exc:
                out[t.id] = {"output": f"(error: {exc})", "mode": "error"}
            done += 1
            print(f"  [{done}/{len(tasks)}] {label} {t.id}", flush=True)
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    RES.mkdir(exist_ok=True)
    if not SUBJECTIVE_TASKS:
        print("no tasks — build the bank first"); return
    runner = {"single": run_single, "ultracode": run_ultracode}[mode]
    res = runner(model, SUBJECTIVE_TASKS)
    fn = RES / f"subj_{mode}_{model}.json"
    fn.write_text(json.dumps(res, indent=1))
    if mode == "ultracode":
        jp = sum(1 for v in res.values() if v.get("mode") == "judge-panel")
        print(f"\njudge-panel used on {jp}/{len(res)} tasks")
    print(f"wrote {fn}")


if __name__ == "__main__":
    main()
