"""Collect the Opus MATH answer files into the {i:{boxed,gt,level}} shape math_judge.py consumes.

Reads bench/results/opus_math_base/<i>.txt and opus_math_ultra/<i>.txt, joins each to its ground
truth + level from math500.json, and writes math_single_opus.json / math_ultracode_opus.json so
`python bench/math_judge.py opus` can score them with the same equivalence judge as flash.

  python bench/collect_opus_math.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "bench" / "data" / "math500.json"
RES = ROOT / "bench" / "results"


def collect(subdir, out_name):
    probs = {p["i"]: p for p in json.loads(DATA.read_text())}
    d = RES / subdir
    out = {}
    missing = 0
    for i, p in probs.items():
        f = d / f"{i}.txt"
        if not f.is_file():
            missing += 1
            continue
        boxed = f.read_text().strip()
        # tolerate an agent that wrapped it in \boxed{...} or $...$
        if boxed.startswith("\\boxed{") and boxed.endswith("}"):
            boxed = boxed[len("\\boxed{"):-1]
        boxed = boxed.strip("$ ").strip()
        out[str(i)] = {"boxed": boxed, "gt": p["answer"], "level": p["level"]}
    (RES / out_name).write_text(json.dumps(out, indent=1))
    return len(out), missing


def main():
    for sub, mode in (("opus_math_base", "single"), ("opus_math_ultra", "ultracode")):
        if not (RES / sub).is_dir() or not any((RES / sub).iterdir()):
            print(f"  {sub}: (no files)"); continue
        name = f"math_{mode}_opus.json"
        n, miss = collect(sub, name)
        print(f"  {sub}: {n} answers -> {name} (missing {miss})")
    print("\n  next: python bench/math_judge.py opus")


if __name__ == "__main__":
    main()
