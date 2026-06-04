"""Fetch ~1000 CoNLL-2003 (NER, test) sentences for ner_coverage_bench.py.

CoNLL-2003 is the canonical named-entity-recognition benchmark. We use it for a PURE-COVERAGE task:
recognizing that "London" is a location is trivial — the challenge is finding EVERY entity scattered
across a corpus larger than one pass. Pulls from the HF datasets-server, reconstructs entity surface
strings from the BIO tags, and writes conll_test_2000.json: a list of {text, entities:[{text,type}]}.

  python bench/data/fetch_conll.py
"""

import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "conll_test_2000.json"
BASE = "https://datasets-server.huggingface.co/rows?dataset=tomaarsen/conll2003&config=default&split=test"
LABELS = ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC", "B-MISC", "I-MISC"]


def _spans(tokens, tags):
    ents, cur, cur_t = [], None, None
    for tok, t in zip(tokens, tags):
        lab = LABELS[t]
        if lab.startswith("B-"):
            if cur:
                ents.append({"text": " ".join(cur), "type": cur_t})
            cur, cur_t = [tok], lab[2:]
        elif lab.startswith("I-") and cur is not None:
            cur.append(tok)
        else:
            if cur:
                ents.append({"text": " ".join(cur), "type": cur_t})
            cur, cur_t = None, None
    if cur:
        ents.append({"text": " ".join(cur), "type": cur_t})
    return ents


def _page(offset, length=100, retries=5):
    import time
    url = f"{BASE}&offset={offset}&length={length}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())["rows"]
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504, 429) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise


def main():
    rows = []
    for offset in range(0, 2000, 100):
        for r in _page(offset):
            x = r["row"]
            toks = x["tokens"]
            if not toks or toks[0] == "-DOCSTART-":
                continue
            rows.append({"text": " ".join(toks), "entities": _spans(toks, x["ner_tags"])})
    OUT.write_text(json.dumps(rows))
    n_ent = sum(len(r["entities"]) for r in rows)
    uniq = len({e["text"].lower() for r in rows for e in r["entities"]})
    print(f"wrote {len(rows)} sentences, {n_ent} entity mentions ({uniq} unique surface strings) -> {OUT}")


if __name__ == "__main__":
    main()
