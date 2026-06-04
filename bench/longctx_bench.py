"""Long-context multi-value retrieval (RULER / multi-needle-in-a-haystack style) — the benchmark
that STRUCTURALLY requires orchestration.

Unlike GSM8K/HumanEval/MATH (atomic, single-context — execution helps, orchestration can't), this is
a *coverage-over-a-corpus* task: N "clearance codes" (CLR-XXXXXX) are scattered across a synthetic
corpus, and the task is to recover EVERY one. A single focused pass dilutes/loses-in-the-middle as
the corpus grows; ultracode's chunk -> fan-out one extractor per section -> reconcile reads all of
it. This is the regime in the harness's own thesis (and the real-repo 0.02 -> 1.00 result), now as a
recognized, fully-reproducible, exactly-scored benchmark with a context-scaling curve.

Synthetic by design (RULER's method): zero external data, deterministic by seed, controllable length
-> the scaling curve is the artifact. Scored by exact set-recall/precision on the planted codes.

  python bench/longctx_bench.py single     deepseek-v4-flash      # single-pass baseline, all sizes
  python bench/longctx_bench.py ultracode  deepseek-v4-flash      # chunk -> fan-out -> reconcile
"""

import random
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultracode.config import UltracodeConfig
from ultracode.corpus import research_corpus
from bench.deepseek_client import DeepSeekClient

RES = Path(__file__).resolve().parent / "results"
SIZES = [30, 90, 180]            # documents = codes to recover (the context-pressure axis)
DOCS_PER_FILE = 8                    # packing -> bounds ultracode fan-out to ~N/8 extractors

# DENSE multi-value: every document carries one clearance code, so the task is to recover ALL N of
# them. This is the honest single-pass failure mode — not truncation, but omission/dilution: asked to
# list N scattered values from a long context, a single pass drops most of them (measured: 180 codes
# in 94k tokens -> recall 0.32, precision 1.0). Each fan-out extractor lists only its section's ~8
# codes (trivially complete), and the reconciled union recovers all N. That gap IS the orchestration.
def needles_for(n_docs):
    return n_docs
CODE_RE = re.compile(r"CLR-[A-Z2-9]{6}")
QUESTION = (
    "Somewhere in this corpus, certain projects have a clearance code written in the form "
    "'The clearance code for Project <Name> is CLR-XXXXXX.' (CLR- followed by exactly 6 chars). "
    "Find EVERY such clearance code anywhere in the corpus and list them ALL, one per line as "
    "'Project <Name>: CLR-XXXXXX'. Completeness matters — do not stop early, do not summarize."
)

_ADJ = "azure crimson silent hollow northern ancient rapid frozen golden quiet distant molten amber " \
       "velvet copper hidden brittle solemn vivid hollow".split()
_NOUN = "harbor falcon meadow cipher lantern glacier ember thicket beacon quartz raven cobalt willow " \
        "summit marsh canyon orchard pylon ridge delta".split()
_FILLER = ("The committee reviewed the quarterly logistics report and noted several routine items. "
           "Maintenance of the eastern conduit proceeded on schedule with no incidents reported. "
           "Staff rotations were confirmed and the supply manifest was reconciled against the ledger. "
           "A brief weather advisory was issued but had no operational impact on the facility. "
           "Routine calibration of the sensor array was completed by the night shift. "
           "The archive index was updated and redundant records were flagged for later review.").split(". ")


def _code(rng):
    alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "CLR-" + "".join(rng.choice(alpha) for _ in range(6))


def make_corpus(n_docs, n_needles, seed):
    rng = random.Random(seed)
    used, needles = set(), {}
    while len(needles) < n_needles:
        name = f"{rng.choice(_ADJ).capitalize()}-{rng.choice(_NOUN).capitalize()}"
        if name in used:
            continue
        used.add(name)
        c = _code(rng)
        if c not in needles.values():
            needles[name] = c
    docs = []
    for i in range(n_docs):
        sents = [rng.choice(_FILLER) for _ in range(rng.randint(4, 7))]
        docs.append([f"memo_{i:04d}", ". ".join(s.strip(". ") for s in sents) + "."])
    # plant each needle into a distinct random doc, at a random sentence boundary
    for name, pos in zip(needles, rng.sample(range(n_docs), n_needles)):
        parts = docs[pos][1].split(". ")
        j = rng.randint(0, len(parts))
        parts.insert(j, f"The clearance code for Project {name} is {needles[name]}")
        docs[pos][1] = ". ".join(p.strip(". ") for p in parts) + "."
    return docs, needles


def score(found, needles):
    gt = set(needles.values())
    tp = found & gt
    return len(tp) / len(gt), (len(tp) / max(len(found), 1)), len(tp), len(gt)


# A single reasoning pass operates on a bounded working set. We declare that budget explicitly: the
# `single_budget` baseline truncates the corpus to BUDGET_CHARS (~6k tokens — generous for one focused
# extraction turn). This is the regime ultracode is FOR — corpus exceeds the pass — and the collapse is
# DETERMINISTIC (it sees min(L, B)), unlike the model's stochastic native-window cliff.
BUDGET_CHARS = 24000


def run_single(client, docs, budget=None):
    corpus = "\n\n".join(f"[{t}]\n{b}" for t, b in docs)
    full = len(corpus)
    if budget and full > budget:
        corpus = corpus[:budget]
    out = client.chat(
        [{"role": "system", "content": "You are a meticulous analyst. Read the ENTIRE corpus and "
          "extract exhaustively. Never truncate or summarize when asked to list everything."},
         {"role": "user", "content": QUESTION + "\n\n=== CORPUS ===\n" + corpus}],
        temperature=0.2, max_tokens=8000)
    ans = type(client)._content(out)
    return set(CODE_RE.findall(ans)), full


def run_ultra(model, docs, cfg):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for k in range(0, len(docs), DOCS_PER_FILE):
            chunk = docs[k:k + DOCS_PER_FILE]
            body = "\n\n".join(f"[{t}]\n{b}" for t, b in chunk)
            (root / f"section_{k // DOCS_PER_FILE:03d}.txt").write_text(body)
        cu = DeepSeekClient(model=model, max_workers=16)
        res = research_corpus(
            str(root), QUESTION, ext=(".txt",), delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn,
            config=cfg, concurrency=16, max_chunk_lines=400, synthesize=True, verify=False)
        text = (res.answer or "") + " " + " ".join(
            f"{f.claim} {f.evidence}" for f in res.findings)
        return set(CODE_RE.findall(text)), res


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    RES.mkdir(exist_ok=True)
    cfg = UltracodeConfig(concurrency=16, max_children=16, reconcile=True)
    rows = []
    print(f"\n=== long-context multi-value retrieval — {mode} {model} "
          f"(dense: N codes in N docs, scaling corpus) ===\n")
    for n_docs in SIZES:
        docs, needles = make_corpus(n_docs, needles_for(n_docs), seed=1000 + n_docs)
        t0 = time.time()
        if mode in ("single", "single_budget"):
            cb = DeepSeekClient(model=model, max_workers=4)
            budget = BUDGET_CHARS if mode == "single_budget" else None
            found, corpus_chars = run_single(cb, docs, budget=budget)
            seen = min(corpus_chars, budget) if budget else corpus_chars
            extra = f"corpus={corpus_chars // 1000}k chars, pass saw {seen // 1000}k"
        else:
            found, res = run_ultra(model, docs, cfg)
            extra = f"{res.chunks_read} sections read"
        rec, prec, tp, gt = score(found, needles)
        dt = time.time() - t0
        rows.append({"n_docs": n_docs, "recall": round(rec, 3), "precision": round(prec, 3),
                     "found": tp, "gt": gt})
        print(f"  n_docs={n_docs:4d}  recall={rec:.2f} ({tp}/{gt})  prec={prec:.2f}  [{extra}, {dt:.0f}s]",
              flush=True)
    import json
    (RES / f"longctx_{mode}_{model}.json").write_text(json.dumps({"dense": True, "rows": rows}, indent=1))
    print(f"\n  saved -> results/longctx_{mode}_{model}.json")


if __name__ == "__main__":
    main()
