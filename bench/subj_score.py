"""Combine the blind subjective-judge verdicts with the solver mapping -> the scoreboard.

Per task the judge returns, for each label A/B/C: rubric_met (criteria satisfied), n_rubric,
constraint_ok (bool), and `best` (the label of the strongest piece). We de-anonymize via the
mapping and report, per solver: mean rubric coverage, constraint-compliance rate, and win-rate
(how often it was judged the single best). Win-rate vs the Opus baseline is the headline for
this subjective regime.

  python bench/subj_score.py <judge_verdicts.json>
"""

import json
import sys
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"
SOLVERS = ["opus", "ds_single", "ds_ultracode"]


def main():
    verdicts = json.loads(Path(sys.argv[1]).read_text())  # {id: {A:{...}, B:{...}, C:{...}, best:"A"}}
    mapping = json.loads((RES / "subj_judge_mapping.json").read_text())  # {id: {solver: label}}
    agg = {s: {"rubric": [], "constraint_ok": 0, "wins": 0, "n": 0} for s in SOLVERS}
    ties = 0
    for tid, v in verdicts.items():
        if tid not in mapping:
            continue
        lab2sol = {lab: sol for sol, lab in mapping[tid].items()}
        best = v.get("best", "")
        for lab, sol in lab2sol.items():
            sc = v.get(lab, {})
            nr = sc.get("n_rubric") or 1
            agg[sol]["rubric"].append((sc.get("rubric_met", 0)) / nr)
            agg[sol]["constraint_ok"] += int(bool(sc.get("constraint_ok", False)))
            agg[sol]["n"] += 1
        if best in lab2sol:
            agg[lab2sol[best]]["wins"] += 1
        else:
            ties += 1
    print(f"{'solver':14}{'rubric%':>9}{'constraint%':>13}{'win-rate':>11}  (n tasks judged)")
    for s in SOLVERS:
        a = agg[s]; n = a["n"] or 1
        rub = sum(a["rubric"]) / len(a["rubric"]) if a["rubric"] else 0
        print(f"{s:14}{rub:>8.1%}{a['constraint_ok']/n:>12.1%}{a['wins']/n:>10.1%}  (n={n})")
    o = agg["opus"]; on = o["n"] or 1
    orub = sum(o["rubric"]) / len(o["rubric"]) if o["rubric"] else 1
    ur = sum(agg["ds_ultracode"]["rubric"]) / len(agg["ds_ultracode"]["rubric"]) if agg["ds_ultracode"]["rubric"] else 0
    sr = sum(agg["ds_single"]["rubric"]) / len(agg["ds_single"]["rubric"]) if agg["ds_single"]["rubric"] else 0
    print(f"\n=== ultracode-flash rubric / opus = {ur/orub:.1%}  |  single-shot / opus = {sr/orub:.1%} ===")
    print(f"=== win-rate: opus {agg['opus']['wins']}/{on}, ultracode {agg['ds_ultracode']['wins']}/{on}, "
          f"single {agg['ds_single']['wins']}/{on}, ties {ties} ===")


if __name__ == "__main__":
    main()
