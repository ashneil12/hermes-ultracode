"""NER coverage over a growing corpus (CoNLL-2003) — a REAL, recognized, PURE-COVERAGE benchmark.

The task: list EVERY named entity (person / organization / location) mentioned anywhere in the corpus.
Per-entity recognition is trivial — the whole difficulty is COVERAGE: as the corpus grows past one
focused pass, a single bounded read can only scan a working set's worth and misses every entity that
lives in the unread tail, while ultracode chunks the corpus and fans out one extractor per section and
unions the result. This is the synthetic multi-value curve, now on real, cited NER data with an exact
gold set. Reasoning is not the bottleneck here (recognizing 'London' is easy) — coverage is — so it
isolates exactly what orchestration is FOR.

Metric: entity-set RECALL = (unique gold entities found anywhere in the output) / (unique gold entities).

  python bench/ner_coverage_bench.py single_budget deepseek-v4-flash
  python bench/ner_coverage_bench.py ultracode      deepseek-v4-flash
"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultracode.config import UltracodeConfig
from bench.deepseek_client import DeepSeekClient

DATA = Path(__file__).resolve().parent / "data" / "conll_test_2000.json"
RES = Path(__file__).resolve().parent / "results"
SIZES = [100, 400, 1000, 2000]      # sentences (the context-pressure axis)
BUDGET_CHARS = 24000
SENTS_PER_FILE = 40
QUESTION = ("List EVERY named entity — every PERSON, ORGANIZATION, and LOCATION — mentioned anywhere "
            "in the text. Output them as a plain list, one entity per line. Be exhaustive: include "
            "every distinct name, do not stop early, do not summarize, do not group.")


def _norm(s):
    return " ".join((s or "").lower().split())


def gold_set(sents):
    return {_norm(e["text"]) for s in sents for e in s["entities"] if _norm(e["text"])}


def recall(output, gold):
    o = _norm(output)
    hits = sum(1 for g in gold if g and re.search(r"\b" + re.escape(g) + r"\b", o))
    return hits / max(len(gold), 1)


def _truncated(resp):
    try:
        return getattr(resp.choices[0], "finish_reason", None) == "length"
    except (AttributeError, IndexError, TypeError):
        return False


def run_single(client, sents, budget):
    corpus = " ".join(s["text"] for s in sents)[:budget]
    msgs = [{"role": "system", "content": "You are a meticulous information extractor. Read the ENTIRE "
             "text and list every named entity exhaustively. Never truncate or summarize."},
            {"role": "user", "content": QUESTION + "\n\n=== TEXT ===\n" + corpus}]
    # the single-pass baseline must measure the model's COVERAGE, not API noise: an empty OR
    # truncated (finish_reason=length) response is an infrastructure artifact, so escalate the
    # output budget and retry. A genuinely-complete short answer (finish_reason=stop) is kept as-is.
    mt, ans = 8000, ""
    for _ in range(4):
        resp = client.chat(msgs, temperature=0.1, max_tokens=mt)
        ans = type(client)._content(resp)
        if ans.strip() and not _truncated(resp):
            return ans
        mt *= 2
    return ans


def run_ultra(model, sents, cfg):
    # The HARNESS primitive does the whole job now: chunk -> fan out one raw enumerator per section
    # -> union+dedupe, with retry_empty refilling any token-starved/flaky chunk (the fix for the
    # silent coverage hole that used to cap recall). We just supply the sections and read .items.
    from ultracode.corpus import enumerate_corpus
    cu = DeepSeekClient(model=model, max_workers=6)
    sections = ["\n".join(s["text"] for s in sents[i:i + SENTS_PER_FILE])
                for i in range(0, len(sents), SENTS_PER_FILE)]
    res = enumerate_corpus(
        sections, "named entity (every PERSON, ORGANIZATION, and LOCATION)",
        delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn, config=cfg,
        concurrency=6, retry_empty=3, single_pass_chars=0)
    return " \n ".join(res.items)


def _measure(mode, sents, gold, cfg, model):
    if mode == "single_budget":
        return recall(run_single(DeepSeekClient(model=model, max_workers=4), sents, BUDGET_CHARS), gold)
    return recall(run_ultra(model, sents, cfg), gold)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single_budget"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 1   # these single-shot coverage points are
    RES.mkdir(exist_ok=True)                              # high-variance; >1 averages for a stable number
    rows = json.loads(DATA.read_text())
    cfg = UltracodeConfig(concurrency=16, max_children=16, reconcile=True)
    out, out_path = [], RES / f"ner_{mode}_{model}.json"
    print(f"\n=== NER coverage (CoNLL-2003) — {mode} {model} (recall of all entities, {runs} run(s)) ===\n")
    for n in SIZES:
        sents = rows[:n]
        gold = gold_set(sents)
        t0 = time.time()
        rs = []
        for _ in range(max(1, runs)):
            try:
                rs.append(_measure(mode, sents, gold, cfg, model))
            except Exception as e:
                print(f"    N={n} error: {type(e).__name__}: {e}", flush=True)
                rs.append(0.0)
        r = sum(rs) / len(rs)
        corpus_k = sum(len(s["text"]) for s in sents) // 1000
        spread = f" (runs {', '.join(f'{x:.2f}' for x in rs)})" if runs > 1 else ""
        out.append({"n_sents": n, "gold": len(gold), "recall": round(r, 3), "runs": rs})
        out_path.write_text(json.dumps({"rows": out}, indent=1))  # checkpoint per size
        print(f"  N={n:4d} sents ({corpus_k:3d}k chars, {len(gold):4d} entities)  recall={r:.3f}{spread}  "
              f"[{time.time()-t0:.0f}s]", flush=True)
    print(f"\n  saved -> {out_path.name}")


if __name__ == "__main__":
    main()
