"""Grade the Opus HotpotQA answers written by wf_opus_hotpot.js, with the same official F1/EM.

Reads bench/results/opus_hotpot/q*/{bounded_k8,bounded_k60,ultra_k60}.ans + gold.json, scores each
condition, and prints the Opus rows for the 4-way HotpotQA spectrum (alongside the flash numbers).

  python bench/grade_opus_hotpot.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.multihop_bench import f1, em, _answer

DIR = Path(__file__).resolve().parent / "results" / "opus_hotpot"


def grade(cond):
    gold = json.loads((DIR / "gold.json").read_text())
    f1s, ems, miss = [], [], 0
    for qi, ans in gold.items():
        f = DIR / f"q{int(qi):02d}" / f"{cond}.ans"
        if not f.is_file():
            miss += 1
            f1s.append(0.0); ems.append(0.0)
            continue
        pred = _answer(f.read_text())
        f1s.append(f1(pred, ans)); ems.append(em(pred, ans))
    n = len(gold)
    return {"f1": round(sum(f1s) / n, 3), "em": round(sum(ems) / n, 3), "n": n, "missing": miss}


def main():
    out = {}
    print("\n=== Opus HotpotQA (graded with the same official F1/EM as flash) ===\n")
    for cond in ("bounded_k8", "bounded_k60", "ultra_k60"):
        if not any(DIR.glob(f"q*/{cond}.ans")):
            print(f"  {cond:12s}: (no answers yet)"); continue
        r = grade(cond)
        out[cond] = r
        print(f"  {cond:12s}: F1={r['f1']:.3f}  EM={r['em']:.3f}  (missing {r['missing']}/{r['n']})")
    if "bounded_k60" in out and "ultra_k60" in out:
        d = out["ultra_k60"]["f1"] - out["bounded_k60"]["f1"]
        print(f"\n  K=60  opus ultra − bounded = {d:+.3f} F1  "
              f"(does orchestration recover buried evidence for a FRONTIER model?)")
    (Path(__file__).resolve().parent / "results" / "multihop_opus.json").write_text(json.dumps(out, indent=1))
    print("\n  saved -> results/multihop_opus.json")


if __name__ == "__main__":
    main()
