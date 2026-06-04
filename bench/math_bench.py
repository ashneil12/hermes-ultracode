"""MATH-500 (competition math, the standard HARD math eval) — saves answers for an equivalence judge.

Unlike GSM8K (grade-school, both models near ceiling), MATH is competition-level: a weak model
struggles, so ultracode's execution-as-evidence (write+run code for the computational parts) has
real room to lift. Answers are LaTeX, so scoring is done by an equivalence judge, not string match —
this runner just produces the answers.

  python bench/math_bench.py single     deepseek-v4-flash 200
  python bench/math_bench.py ultracode  deepseek-v4-flash 200   # execution_assist on
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

DATA = Path(__file__).resolve().parent / "data" / "math500.json"
RES = Path(__file__).resolve().parent / "results"
DIRECTIVE = "\n\nSolve it. Put ONLY your final answer inside \\boxed{...} at the end."


def _boxed(text):
    # extract the last \boxed{...} (balanced braces)
    s = text or ""
    out, i = "", s.rfind("\\boxed")
    if i == -1:
        return (s.strip().splitlines() or [""])[-1][:120]
    j = s.find("{", i)
    if j == -1:
        return ""
    depth, k = 0, j
    while k < len(s):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                return s[j + 1:k].strip()
        k += 1
    return s[j + 1:].strip()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    RES.mkdir(exist_ok=True)
    probs = json.loads(DATA.read_text())[:n]
    cfg = UltracodeConfig(concurrency=8, max_children=6, max_finders=4, execution_assist=(mode == "ultracode"))

    def solve(p):
        if mode == "single":
            cb = DeepSeekClient(model=model, max_workers=2)
            o = cb.chat([{"role": "system", "content": "You are an expert at competition mathematics."},
                         {"role": "user", "content": p["problem"] + DIRECTIVE}], temperature=0.2, max_tokens=2500)
            ans = type(cb)._content(o)
        else:
            cu = DeepSeekClient(model=model, max_workers=8)
            res = run(p["problem"] + DIRECTIVE, delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn,
                      config=cfg, enable_ledger=False, run_id="math")
            ans = res.answer
        return p["i"], {"boxed": _boxed(ans), "gt": p["answer"], "level": p["level"]}

    out, done = {}, 0
    with ThreadPoolExecutor(max_workers=8 if mode == "single" else 5) as ex:
        futs = [ex.submit(solve, p) for p in probs]
        for f in as_completed(futs):
            try:
                i, r = f.result(); out[i] = r
            except Exception:
                pass
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(probs)} ...", flush=True)
    (RES / f"math_{mode}_{model}.json").write_text(json.dumps(out, indent=1))
    print(f"\n=== MATH {mode} {model}: {len(out)} answers saved (judge for equivalence next) ===", flush=True)


if __name__ == "__main__":
    main()
