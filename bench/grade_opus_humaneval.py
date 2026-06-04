"""Grade the Opus HumanEval solution files written by the workflow against the official tests.

Reads bench/results/opus_he_base/HumanEval_<i>.py and opus_he_ultra/HumanEval_<i>.py, runs each
against the canonical check() from HumanEval.jsonl, and reports pass@1. Deterministic grading —
the model only generated code; correctness is decided by the runtime, same as the flash runs.

  python bench/grade_opus_humaneval.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultracode.execute import run_python

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "bench" / "data" / "HumanEval.jsonl"
RES = ROOT / "bench" / "results"


def _strip_fences(code):
    # tolerate an agent that left a ```python fence despite instructions
    m = re.search(r"```(?:python)?\s*(.*?)```", code, re.S)
    return (m.group(1) if m else code).strip()


def grade(subdir):
    probs = [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()]
    d = RES / subdir
    ok = missing = 0
    fails = []
    for k, p in enumerate(probs):
        f = d / f"HumanEval_{k}.py"
        if not f.is_file():
            missing += 1
            fails.append(f"{k}:missing")
            continue
        code = _strip_fences(f.read_text())
        prog = f"{code}\n\n{p['test']}\n\ncheck({p['entry_point']})\n"
        r = run_python(prog, timeout=10.0)
        if r.ok:
            ok += 1
        else:
            fails.append(str(k))
    n = len(probs)
    return {"pass": ok, "n": n, "acc": round(ok / n, 4), "missing": missing,
            "failed_ids": fails[:40]}


def main():
    print("\n=== Opus HumanEval (graded by official tests, same as flash) ===\n")
    out = {}
    for cond, sub in (("base", "opus_he_base"), ("ultra", "opus_he_ultra")):
        if not (RES / sub).is_dir() or not any((RES / sub).iterdir()):
            print(f"  {cond:5s}: (no files in {sub})"); continue
        r = grade(sub)
        out[cond] = r
        print(f"  opus-{cond:5s}: pass@1 = {r['pass']}/{r['n']} = {r['acc']:.3f}   "
              f"(missing {r['missing']})")
    if "base" in out and "ultra" in out:
        print(f"\n  opus ultra - base = {out['ultra']['acc'] - out['base']['acc']:+.3f}")
    (RES / "humaneval_opus.json").write_text(json.dumps(out, indent=1))
    print("\n  saved -> results/humaneval_opus.json")


if __name__ == "__main__":
    main()
