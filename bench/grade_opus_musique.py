"""Grade the Opus MuSiQue answers (wf_opus_musique.js) with alias-aware official F1/EM.

  python bench/grade_opus_musique.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.multihop_bench import f1 as _f1, em as _em, _answer

DIR = Path(__file__).resolve().parent / "results" / "opus_musique"


def _best(fn, pred, g):
    cands = [g["answer"], *g.get("aliases", [])] or [g["answer"]]
    return max(fn(pred, c) for c in cands)


def grade(cond):
    gold = json.loads((DIR / "gold.json").read_text())
    f1s, ems, miss = [], [], 0
    for qi, g in gold.items():
        f = DIR / f"q{int(qi):02d}" / f"{cond}.ans"
        if not f.is_file():
            miss += 1; f1s.append(0.0); ems.append(0.0); continue
        pred = _answer(f.read_text())
        f1s.append(_best(_f1, pred, g)); ems.append(_best(_em, pred, g))
    n = len(gold)
    return {"f1": round(sum(f1s) / n, 3), "em": round(sum(ems) / n, 3), "n": n, "missing": miss}


def main():
    out = {}
    print("\n=== Opus MuSiQue (alias-aware official F1/EM) ===\n")
    for cond in ("bounded_k8", "bounded_k120", "ultra_k120"):
        if not any(DIR.glob(f"q*/{cond}.ans")):
            print(f"  {cond:13s}: (no answers yet)"); continue
        r = grade(cond); out[cond] = r
        print(f"  {cond:13s}: F1={r['f1']:.3f}  EM={r['em']:.3f}  (missing {r['missing']}/{r['n']})")
    if "bounded_k120" in out and "ultra_k120" in out:
        d = out["ultra_k120"]["f1"] - out["bounded_k120"]["f1"]
        print(f"\n  K=120  opus ultra − bounded = {d:+.3f} F1  "
              f"(orchestration recovery for a frontier model on ANTI-SHORTCUT questions)")
    (Path(__file__).resolve().parent / "results" / "musique_opus.json").write_text(json.dumps(out, indent=1))
    print("\n  saved -> results/musique_opus.json")


if __name__ == "__main__":
    main()
