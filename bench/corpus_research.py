"""Where parallel deep-research organization GENUINELY wins: a corpus too large for
one focused pass.

The parametric-knowledge benchmarks (research_bench, coverage_bench) showed a capable
model SATURATES a single pass on well-known topics — orchestration can't beat a ceiling
already reached. The real win is the regime the single pass can't hold: a large corpus
of FABRICATED facts (so parametric knowledge can't shortcut — the only way to recover a
fact is to actually READ the chunk it lives in). A single pass over the whole corpus is
attention-limited (lost-in-the-middle); N focused extractors each attend fully to one
chunk, and the union recovers far more. This is the research analog of repo-scale audit.

Usage: python bench/corpus_research.py [model] [n_docs] [chunk_docs]
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.deepseek_client import DeepSeekClient

# Deterministic fabricated facts: unique codename + attribute + value. Parametric
# knowledge cannot know these — recovery REQUIRES reading the doc. Signature = both tokens.
_CODENAMES = [
    "Zephyr", "Quasar", "Lighthouse", "Obsidian", "Tundra", "Marigold", "Helios", "Basalt",
    "Cinder", "Driftwood", "Ember", "Fjord", "Granite", "Halcyon", "Ivory", "Juniper",
    "Kelvin", "Lattice", "Monsoon", "Nimbus", "Onyx", "Pinnacle", "Quill", "Riptide",
    "Sable", "Talon", "Umbra", "Vellum", "Willow", "Xenon", "Yarrow", "Zenith",
    "Aster", "Bramble", "Cobalt", "Dune", "Estuary", "Flint", "Gossamer", "Harbor",
]
_ATTRS = [
    ("handshake timeout", "{}ms"), ("max shard count", "{}"), ("retry ceiling", "{} attempts"),
    ("token budget", "{}k"), ("quorum size", "{} nodes"), ("cache TTL", "{} seconds"),
    ("rollout cohort", "{}%"), ("nonce width", "{}-bit"), ("batch window", "{}ms"),
    ("replication factor", "{}x"),
]


def make_corpus(n_docs):
    """Return (corpus_text, facts) where each fact is (name, [sig_tokens])."""
    docs, facts = [], []
    filler = (
        "This brief documents internal design decisions and operational notes for the program. "
        "It covers background context, prior art, deployment considerations, rollback procedures, "
        "stakeholder sign-off, observability hooks, and assorted maintenance guidance. The team "
        "reviewed alternatives and recorded the rationale for the chosen configuration below. "
    ) * 14  # ~5k chars of plausible, fact-free filler per doc
    for i in range(n_docs):
        name = _CODENAMES[i % len(_CODENAMES)] + ("" if i < len(_CODENAMES) else f"-{i//len(_CODENAMES)+1}")
        attr, vfmt = _ATTRS[i % len(_ATTRS)]
        val = vfmt.format(100 + i * 7)  # deterministic distinctive value
        fact_sentence = f"DECISION: Project {name} sets its {attr} to {val}."
        # bury the one fact in the middle of the filler (lost-in-the-middle stress)
        body = filler[:2500] + " " + fact_sentence + " " + filler[2500:]
        docs.append(f"=== Document {i+1}: Project {name} ===\n{body}")
        sig_val = val.replace("k", "").replace("%", "").replace("-bit", "").replace("ms", "").replace("x", "").split()[0]
        facts.append((name.lower(), [name.lower(), sig_val]))
    return "\n\n".join(docs), facts


def score(answer, facts):
    a = (answer or "").lower()
    found = [n for n, sig in facts if all(tok.lower() in a for tok in sig)]
    return len(found) / len(facts), found


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    n_docs = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    chunk_docs = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    # one context window's worth of chars the single pass can actually see. A single call
    # CANNOT see beyond its context, full stop — beyond this you MUST chunk. (~100k tokens.)
    baseline_budget = int(sys.argv[4]) if len(sys.argv) > 4 else 400_000
    corpus, facts = make_corpus(n_docs)
    docs = corpus.split("\n\n=== ")
    docs = [docs[0]] + ["=== " + d for d in docs[1:]]
    print(f"corpus: {n_docs} docs, {len(corpus)} chars (~{len(corpus)//4} tokens), {len(facts)} fabricated facts; "
          f"baseline context budget={baseline_budget} chars (~{baseline_budget//4} tokens)", flush=True)

    # --- baseline: ONE pass; sees only what fits ONE context window ---
    cb = DeepSeekClient(model=model, max_workers=4)
    seen = corpus[:baseline_budget]
    facts_in_view = [n for n, sig in facts if all(t in seen.lower() for t in sig)]
    truncated = len(corpus) > baseline_budget
    q = ("The corpus below contains many project briefs. Each brief states exactly one DECISION line "
         "with a project codename and a specific configured value. Extract EVERY project's codename and "
         "its stated value. List all of them — do not skip any.\n\nCORPUS:\n" + seen)
    out = cb.chat([{"role": "system", "content": "Extract exhaustively and precisely."},
                   {"role": "user", "content": q}], temperature=0.2, max_tokens=4000)
    b_ans = type(cb)._content(out)
    b_cov, b_found = score(b_ans, facts)
    print(f"BASELINE (1 pass, {'TRUNCATED to context: ' if truncated else ''}{len(facts_in_view)}/{len(facts)} facts "
          f"physically in view): coverage={b_cov:.2f} ({len(b_found)}/{len(facts)})  "
          f"tokens={cb.usage.snapshot()['total_tokens']//1000}k", flush=True)

    # --- orchestrated: chunk the corpus, one focused extractor per chunk, union ---
    chunks = ["\n\n".join(docs[i:i + chunk_docs]) for i in range(0, len(docs), chunk_docs)]
    cu = DeepSeekClient(model=model, max_workers=12)
    tasks = [{"goal": ("Extract EVERY project codename and its stated DECISION value from this section. "
                       "Be exhaustive; quote the codename and value verbatim.\n\nSECTION:\n" + ch)}
             for ch in chunks]
    results = cu.delegate_fn(tasks=tasks, parent_agent=None, role="extractor")
    import json
    parts = []
    try:
        rs = json.loads(results)["results"]
        parts = [r.get("summary", "") for r in rs]
    except Exception:
        parts = [str(results)]
    union = "\n".join(parts)
    u_cov, u_found = score(union, facts)
    print(f"ORCHESTRATED ({len(chunks)} focused chunk-extractors): coverage={u_cov:.2f} "
          f"({len(u_found)}/{len(facts)})  tokens={cu.usage.snapshot()['total_tokens']//1000}k", flush=True)
    print(f"\n=== {model}: baseline={b_cov:.2f}  orchestrated={u_cov:.2f}  lift={u_cov-b_cov:+.2f} ===", flush=True)
    print(f"   facts only orchestration found: {sorted(set(u_found)-set(b_found))[:20]}", flush=True)


if __name__ == "__main__":
    main()
