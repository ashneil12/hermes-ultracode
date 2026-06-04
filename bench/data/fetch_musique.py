"""Fetch a 200-question MuSiQue (answerable, validation) sample for musique_bench.py.

MuSiQue is a multi-hop QA benchmark *composed* to defeat single-hop shortcuts (2-4 hops; you can't
answer 'the spouse of the Green performer' from memory — you must chain). Pulls from the HuggingFace
datasets-server (JSON), keeps answerable questions, flattens each question's 20 paragraphs and marks
the supporting (gold) titles, and writes musique_dev_200.json. (CC BY 4.0; fetched, not redistributed.)

  python bench/data/fetch_musique.py
"""

import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "musique_dev_200.json"
BASE = ("https://datasets-server.huggingface.co/rows?dataset=dgslibisey/MuSiQue"
        "&config=default&split=validation")


def _page(offset, length=100):
    with urllib.request.urlopen(f"{BASE}&offset={offset}&length={length}", timeout=60) as r:
        return json.loads(r.read())["rows"]


def main():
    rows, offset = [], 0
    while len(rows) < 200 and offset < 600:
        for r in _page(offset):
            x = r["row"]
            if not x.get("answerable"):
                continue
            paras = [{"title": p["title"], "text": p["paragraph_text"]} for p in x["paragraphs"]]
            gold = sorted({p["title"] for p in x["paragraphs"] if p["is_supporting"]})
            rows.append({
                "id": x["id"], "question": x["question"], "answer": x["answer"],
                "aliases": x.get("answer_aliases", []), "hops": len(x["question_decomposition"]),
                "paras": paras, "gold_titles": gold,
            })
            if len(rows) >= 200:
                break
        offset += 100
    OUT.write_text(json.dumps(rows))
    hops = {}
    for r in rows:
        hops[r["hops"]] = hops.get(r["hops"], 0) + 1
    print(f"wrote {len(rows)} answerable questions ({sum(len(r['paras']) for r in rows)} paragraphs) -> {OUT}")
    print(f"  hop distribution: {dict(sorted(hops.items()))}")


if __name__ == "__main__":
    main()
