"""Cognitive head-to-head: OPUS baseline vs DeepSeek+ULTRACODE (and DeepSeek single-shot).

The benchmark behind the goal: how close does ultracode-on-a-weak-model (DeepSeek flash)
get to baseline Opus on genuinely reasoning-hard tasks? Every solver's FINAL answer is scored
the SAME objective way (signature match against ground truth). Reports per-category + overall
accuracy and the headline RATIO  ultracode-flash / opus-baseline  (target 0.70-0.80).

  python bench/cognitive_bench.py ultracode deepseek-v4-flash   # run the harness, save results
  python bench/cognitive_bench.py baseline  deepseek-v4-flash   # single-shot DeepSeek
  python bench/cognitive_bench.py report                        # combine saved results + opus answers
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from bench.cognitive_tasks import COGNITIVE_TASKS
from bench.deepseek_client import DeepSeekClient

RESULTS = Path(__file__).resolve().parent / "results"
ANSWER_DIRECTIVE = ("\n\nReason carefully, step by step. Then end with exactly one line:\n"
                    "FINAL ANSWER: <your final answer, stated concisely>")


def is_correct(answer: str, task) -> bool:
    a = (answer or "").lower()
    return any(all(kw.lower() in a for kw in variant) for variant in task.signatures)


def _agg(rows):
    """rows: list of (task, correct_bool). Returns (overall_acc, per_category_dict)."""
    by_cat = {}
    for t, ok in rows:
        c = by_cat.setdefault(t.category, [0, 0])
        c[0] += int(bool(ok)); c[1] += 1
    overall = sum(int(bool(ok)) for _, ok in rows) / max(len(rows), 1)
    return overall, {k: (v[0] / v[1], v[1]) for k, v in by_cat.items()}


def _parallel(tasks, fn, task_workers, label):
    """Run fn(task)->dict over tasks with a task-level pool; print as each completes."""
    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=task_workers) as ex:
        futs = {ex.submit(fn, t): t for t in tasks}
        for f in as_completed(futs):
            t = futs[f]
            try:
                out[t.id] = f.result()
            except Exception as exc:
                out[t.id] = {"answer": f"(error: {exc})", "correct": False}
            done += 1
            print(f"  [{done}/{len(tasks)}] {'OK ' if out[t.id].get('correct') else 'XX '} {label} {t.id:42}", flush=True)
    return out


def run_ultracode(model, tasks, cfg, task_workers=5):
    def one(t):
        cu = DeepSeekClient(model=model, max_workers=12)
        res = run(t.prompt + ANSWER_DIRECTIVE, delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn,
                  config=cfg, enable_ledger=False, run_id=t.id)
        ans = res.answer or ""
        return {"answer": ans, "correct": is_correct(ans, t), "mode": res.mode,
                "tokens": cu.usage.snapshot()["total_tokens"]}
    return _parallel(tasks, one, task_workers, "ULTRA")


def run_baseline(model, tasks, task_workers=10):
    def one(t):
        cb = DeepSeekClient(model=model, max_workers=4)
        o = cb.chat([{"role": "system", "content": "Solve the problem with careful step-by-step reasoning."},
                     {"role": "user", "content": t.prompt + ANSWER_DIRECTIVE}], temperature=0.3, max_tokens=4000)
        ans = type(cb)._content(o) or ""
        return {"answer": ans, "correct": is_correct(ans, t)}
    return _parallel(tasks, one, task_workers, "BASE ")


def _print_table(title, overall, per_cat):
    print(f"\n### {title}: overall = {overall:.3f}")
    for cat, (acc, n) in sorted(per_cat.items()):
        print(f"    {cat:24} {acc:.2f}  (n={n})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    RESULTS.mkdir(exist_ok=True)
    tasks = COGNITIVE_TASKS[:limit] if limit else COGNITIVE_TASKS
    if not tasks:
        print("No tasks loaded — populate bench/cognitive_tasks.py first."); return

    if mode in ("ultracode", "ultracode_exec"):
        exec_assist = mode == "ultracode_exec"
        cfg = UltracodeConfig(concurrency=12, max_children=8, max_finders=6, execution_assist=exec_assist)
        res = run_ultracode(model, tasks, cfg)
        suffix = "_exec" if exec_assist else ""
        (RESULTS / f"cog_ultracode{suffix}_{model}.json").write_text(json.dumps(res, indent=1))
        rows = [(t, res[t.id]["correct"]) for t in tasks]
        overall, per_cat = _agg(rows)
        _print_table(f"ULTRACODE{'+exec' if exec_assist else ''} {model}", overall, per_cat)

    elif mode == "baseline":
        res = run_baseline(model, tasks)
        (RESULTS / f"cog_baseline_{model}.json").write_text(json.dumps(res, indent=1))
        rows = [(t, res[t.id]["correct"]) for t in tasks]
        overall, per_cat = _agg(rows)
        _print_table(f"BASELINE single-shot {model}", overall, per_cat)

    elif mode == "report":
        # combine: opus answers (mine) + ultracode + baseline, print ratio
        idx = {t.id: t for t in tasks}
        def score_file(path, key="answer"):
            if not Path(path).exists():
                return None
            data = json.loads(Path(path).read_text())
            rows = [(idx[i], is_correct(data[i].get(key, ""), idx[i])) for i in data if i in idx]
            return _agg(rows)
        opus = score_file(RESULTS / "cog_opus_answers.json")
        ultra = score_file(RESULTS / f"cog_ultracode_{model}.json")
        base = score_file(RESULTS / f"cog_baseline_{model}.json")
        if opus: _print_table("OPUS baseline (Claude)", *opus)
        if ultra: _print_table(f"ULTRACODE {model}", *ultra)
        if base: _print_table(f"BASELINE single-shot {model}", *base)
        if opus and ultra and opus[0] > 0:
            print(f"\n=== HEADLINE: ultracode-flash / opus-baseline = {ultra[0]/opus[0]:.2%} "
                  f"(target 70-80%) ===")
        if opus and base and opus[0] > 0:
            print(f"=== single-shot flash / opus = {base[0]/opus[0]:.2%}  "
                  f"(ultracode lift over single-shot: {(ultra[0]-base[0]):+.3f}) ===" if ultra else "")


if __name__ == "__main__":
    main()
