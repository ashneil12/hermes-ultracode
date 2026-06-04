"""Assemble anonymized per-task judge inputs for the subjective benchmark.

For each task: gather the three solver outputs (opus baseline from files, ds_single,
ds_ultracode), shuffle them to labels A/B/C deterministically-per-task (no position bias,
no true randomness needed), and write a judge file with the brief + rubric + constraints +
the three anonymized outputs. A separate mapping file records which label is which solver,
so the judge stays blind. The judge scores each on the rubric (criteria met / N), flags
constraint violations, and picks the best — comparative judgment over absolute.
"""

import hashlib
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.subjective_tasks import SUBJECTIVE_TASKS

RES = Path(__file__).resolve().parent / "results"
PIECES = RES / "opus_pieces"
JDIR = RES / "subj_judge"
MODEL = "deepseek-v4-flash"


def _order(tid):
    # deterministic per-task permutation of the 3 solvers -> labels A,B,C
    solvers = ["opus", "ds_single", "ds_ultracode"]
    return sorted(solvers, key=lambda s: hashlib.md5(f"{tid}:{s}".encode()).hexdigest())


def main():
    single = json.loads((RES / f"subj_single_{MODEL}.json").read_text())
    ultra = json.loads((RES / f"subj_ultracode_{MODEL}.json").read_text())
    JDIR.mkdir(exist_ok=True)
    mapping = {}
    n = 0
    for t in SUBJECTIVE_TASKS:
        opus_f = PIECES / f"{t.id}.md"
        outs = {
            "opus": opus_f.read_text().strip() if opus_f.exists() else "",
            "ds_single": single.get(t.id, {}).get("output", ""),
            "ds_ultracode": ultra.get(t.id, {}).get("output", ""),
        }
        if not all(outs.values()):
            continue  # skip tasks missing any output (judge needs all three)
        order = _order(t.id)
        labels = dict(zip(["A", "B", "C"], order))           # A/B/C -> solver
        anon = {lab: outs[sol] for lab, sol in labels.items()}
        (JDIR / f"{t.id}.json").write_text(json.dumps({
            "id": t.id, "category": t.category, "brief": t.brief,
            "rubric": t.rubric, "constraints": t.constraints, "outputs": anon,
        }, indent=1))
        mapping[t.id] = {v: k for k, v in labels.items()}     # solver -> label
        n += 1
    (RES / "subj_judge_mapping.json").write_text(json.dumps(mapping, indent=1))
    (RES / "subj_judge_ids.json").write_text(json.dumps(sorted(mapping), indent=1))
    print(f"wrote {n} judge inputs to {JDIR} (+ blind mapping)")


if __name__ == "__main__":
    main()
