"""Precompute the MuSiQue inputs for the Opus spectrum workflow (mirror of prep_opus_hotpot.py).

Same questions/seeds as musique_bench.py (seed 9000+qi). For each of the first N questions writes
(under bench/results/opus_musique/q{idx}/): question.txt, bounded_k8.txt, bounded_k120.txt (truncated to
the working set), and sec_NNN.txt (the full K=120 haystack split for the fan-out readers). gold.json
stores answer + aliases for alias-aware grading.

  python bench/prep_opus_musique.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.musique_bench import DATA, build_haystack, BUDGET_CHARS

N_EVAL = 12
PARAS_PER_SECTION = 15
OUT = Path(__file__).resolve().parent / "results" / "opus_musique"


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
        gold[str(qi)] = {"answer": item["answer"], "aliases": item.get("aliases", [])}
        for k, tag in ((8, "bounded_k8"), (120, "bounded_k120")):
            hay = build_haystack(item, pool, k, seed=9000 + qi)
            (d / f"{tag}.txt").write_text(
                f"QUESTION: {item['question']}\n\n=== PARAGRAPHS ===\n{_fmt(hay)[:BUDGET_CHARS]}")
        hay120 = build_haystack(item, pool, 120, seed=9000 + qi)
        for si in range(0, len(hay120), PARAS_PER_SECTION):
            (d / f"sec_{si // PARAS_PER_SECTION:03d}.txt").write_text(_fmt(hay120[si:si + PARAS_PER_SECTION]))
    (OUT / "gold.json").write_text(json.dumps(gold, indent=1))
    nsec = len(list((OUT / "q00").glob("sec_*.txt")))
    print(f"prepped {N_EVAL} questions -> {OUT}  (~{nsec} sections/q at K=120)")


if __name__ == "__main__":
    main()
