"""GSM8K (grade-school math) — DeepSeek single-shot vs DeepSeek + ultracode (execution-as-evidence).

A recognized benchmark with objective numeric ground truth. The thesis: a weak model's arithmetic
slips, but ultracode's execution-as-evidence lets it WRITE+RUN the computation — so it should lift
flash markedly, toward frontier scores. Standard last-number extraction + exact match (GSM8K eval).

  python bench/gsm8k_bench.py single     deepseek-v4-flash 200
  python bench/gsm8k_bench.py ultracode  deepseek-v4-flash 200   # execution_assist on
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultracode.config import UltracodeConfig
from ultracode.harness import run
from bench.deepseek_client import DeepSeekClient

DATA = Path(__file__).resolve().parent / "data" / "gsm8k_test.jsonl"
RES = Path(__file__).resolve().parent / "results"
_NUM = re.compile(r"-?\$?\d[\d,]*\.?\d*")
DIRECTIVE = "\n\nSolve it, then end with: #### <the final numeric answer>"


def _gt(ans):  # ground truth = the number after ####
    return _norm(ans.split("####")[-1])


def _norm(s):
    m = _NUM.findall(s or "")
    if not m:
        return None
    v = m[-1].replace(",", "").replace("$", "").rstrip(".")
    try:
        f = float(v)
        return int(f) if f == int(f) else round(f, 4)
    except ValueError:
        return None


def _extract(text):
    # prefer the number right after ####, else the last number in the text
    if "####" in (text or ""):
        return _norm(text.split("####")[-1])
    return _norm(text)


def load(n):
    rows = [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()]
    return [{"q": r["question"], "gt": _gt(r["answer"])} for r in rows[:n]]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    RES.mkdir(exist_ok=True)
    tasks = load(n)
    cfg = UltracodeConfig(concurrency=8, max_children=6, max_finders=4, execution_assist=(mode == "ultracode"))

    def solve(t):
        if mode == "single":
            cb = DeepSeekClient(model=model, max_workers=2)
            o = cb.chat([{"role": "system", "content": "Solve the math problem step by step."},
                         {"role": "user", "content": t["q"] + DIRECTIVE}], temperature=0.2, max_tokens=2000)
            ans = type(cb)._content(o)
        else:
            cu = DeepSeekClient(model=model, max_workers=8)
            res = run(t["q"] + DIRECTIVE, delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn,
                      config=cfg, enable_ledger=False, run_id="gsm8k")
            ans = res.answer
        return _extract(ans) == t["gt"]

    ok = done = 0
    with ThreadPoolExecutor(max_workers=8 if mode == "single" else 5) as ex:
        futs = [ex.submit(solve, t) for t in tasks]
        for f in as_completed(futs):
            try:
                ok += int(bool(f.result()))
            except Exception:
                pass
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(tasks)} ... {ok} correct so far", flush=True)
    acc = ok / len(tasks)
    print(f"\n=== GSM8K {mode} {model}: {ok}/{len(tasks)} = {acc:.3f} ===", flush=True)
    (RES / f"gsm8k_{mode}_{model}.json").write_text(json.dumps({"correct": ok, "n": len(tasks), "acc": acc}))


if __name__ == "__main__":
    main()
