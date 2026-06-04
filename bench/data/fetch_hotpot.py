"""Fetch a 200-question HotpotQA (distractor, validation) sample for multihop_bench.py.

Pulls rows from the HuggingFace datasets-server (JSON, no parquet/datasets lib needed), flattens each
question's 10 paragraphs and marks the gold (supporting-fact) titles, and writes hotpot_dev_200.json.
HotpotQA is CC BY-SA 4.0; this fetches it at run time rather than redistributing it.

  python bench/data/fetch_hotpot.py
"""

import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "hotpot_dev_200.json"
BASE = ("https://datasets-server.huggingface.co/rows?dataset=hotpotqa/hotpot_qa"
        "&config=distractor&split=validation")


def _page(offset, length=100):
    url = f"{BASE}&offset={offset}&length={length}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())["rows"]


def main():
    rows = []
    for offset in (0, 100):
        for r in _page(offset):
            x = r["row"]
            ctx = x["context"]
            paras = [{"title": t, "text": " ".join(s)} for t, s in zip(ctx["title"], ctx["sentences"])]
            rows.append({
                "id": x["id"], "question": x["question"], "answer": x["answer"], "level": x["level"],
                "paras": paras, "gold_titles": sorted(set(x["supporting_facts"]["title"])),
            })
    OUT.write_text(json.dumps(rows))
    print(f"wrote {len(rows)} questions ({sum(len(r['paras']) for r in rows)} paragraphs) -> {OUT}")


if __name__ == "__main__":
    main()
