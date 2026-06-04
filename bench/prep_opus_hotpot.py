"""Precompute the exact HotpotQA inputs for the Opus spectrum workflow.

Uses the SAME questions and seeds as multihop_bench.py so the Opus run is apples-to-apples with flash.
For each of the first N questions, writes (under bench/results/opus_hotpot/q{idx}/):
  question.txt          the question
  bounded_k8.txt        QUESTION + the K=8 haystack truncated to the 6k-tok working set
  bounded_k60.txt       QUESTION + the K=60 haystack truncated to the working set (gold often cut off)
  sec_000.txt ...       the FULL K=60 haystack split into sections (for the ultracode fan-out readers)
and bench/results/opus_hotpot/gold.json (idx -> gold answer) for local F1/EM grading.

  python bench/prep_opus_hotpot.py
"""

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.multihop_bench import DATA, build_haystack, BUDGET_CHARS

N_EVAL = 12
PARAS_PER_SECTION = 15          # ~5 sections at K=60 -> ~6 Opus agents/question for ultracode
OUT = Path(__file__).resolve().parent / "results" / "opus_hotpot"


def _fmt(hay):
    return "\n\n".join(f"== {p['title']} ==\n{p['text']}" for p in hay)


def main():
    rows = json.loads(DATA.read_text())
    pool = [p for r in rows for p in r["paras"]]
    gold = {}
    for qi, item in enumerate(rows[:N_EVAL]):
        d = OUT / f"q{qi:02d}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "question.txt").write_text(item["question"])
        gold[str(qi)] = item["answer"]
        for k, tag in ((8, "bounded_k8"), (60, "bounded_k60")):
            hay, _ = build_haystack(item, pool, k, seed=7000 + qi)
            corpus = _fmt(hay)[:BUDGET_CHARS]
            (d / f"{tag}.txt").write_text(f"QUESTION: {item['question']}\n\n=== PARAGRAPHS ===\n{corpus}")
        # full K=60 haystack, split into sections for the fan-out readers
        hay60, _ = build_haystack(item, pool, 60, seed=7000 + qi)
        for si in range(0, len(hay60), PARAS_PER_SECTION):
            (d / f"sec_{si // PARAS_PER_SECTION:03d}.txt").write_text(_fmt(hay60[si:si + PARAS_PER_SECTION]))
    (OUT / "gold.json").write_text(json.dumps(gold, indent=1))
    print(f"prepped {N_EVAL} questions -> {OUT}")
    nsec = len(list((OUT / 'q00').glob('sec_*.txt')))
    print(f"  ~{nsec} sections/question at K=60 (PARAS_PER_SECTION={PARAS_PER_SECTION})")


if __name__ == "__main__":
    main()
