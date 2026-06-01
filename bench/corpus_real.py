"""REAL-corpus deep research: chunk-extractors read ACTUAL files from a big codebase.

Unlike corpus_research.py (synthetic fabricated facts), this points the corpus machinery
at the real hermes codebase (agent/ + acp_adapter/, ~69k LOC across 112 files) and asks
an exhaustive find-all whose ground truth is grep-derived: every class with a common
suffix. A single truncated pass sees only the head of the corpus; chunked extractors
read all of it. Scores coverage of the synthesized answer AND the extraction union.

Usage: python bench/corpus_real.py [model] [baseline_budget_chars]
"""

import os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.corpus import research_corpus
from bench.deepseek_client import DeepSeekClient

ROOT = "/Users/ash/Projects/vanilla-hermes-agent"
SUBTREES = ("agent", "acp_adapter")
SUFFIX = r"(?:Adapter|Client|Error|Exception|Manager|Handler|Runtime|Result|Config|Registry|Provider|Session|Builder|Store|Cache)"
_CLASS = re.compile(rf"^class ([A-Za-z_][A-Za-z0-9_]*{SUFFIX})\b", re.M)
QUESTION = (
    "Enumerate every Python class whose name ends in Adapter, Client, Error, Exception, Manager, Handler, "
    "Runtime, Result, Config, Registry, Provider, Session, Builder, Store, or Cache that is DEFINED in this "
    "codebase (look for `class NAME...` definitions). For each, give its exact name and a one-line note on "
    "what it represents."
)


def ground_truth():
    names = set()
    for sub in SUBTREES:
        for dp, _, files in os.walk(os.path.join(ROOT, sub)):
            for fn in files:
                if fn.endswith(".py"):
                    try:
                        names.update(_CLASS.findall(open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()))
                    except OSError:
                        pass
    return names


def coverage(text, names):
    t = (text or "").lower()
    found = {n for n in names if n.lower() in t}
    return len(found) / max(len(names), 1), found


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 200_000
    names = ground_truth()
    print(f"ground truth: {len(names)} classes across {SUBTREES} in {ROOT}", flush=True)

    # assemble the corpus text (real files) for the baseline single pass
    files = []
    for sub in SUBTREES:
        for dp, _, fs in os.walk(os.path.join(ROOT, sub)):
            for fn in sorted(fs):
                if fn.endswith(".py"):
                    files.append(os.path.join(dp, fn))
    corpus = "\n\n".join(f"### {os.path.relpath(f, ROOT)}\n" + open(f, encoding="utf-8", errors="replace").read() for f in sorted(files))
    print(f"corpus: {len(files)} files, {len(corpus)} chars (~{len(corpus)//4} tokens); baseline budget {budget} chars", flush=True)

    # --- baseline: ONE pass, sees only what fits one context window ---
    cb = DeepSeekClient(model=model, max_workers=4)
    seen = corpus[:budget]
    in_view, _ = coverage(seen, names)
    out = cb.chat([{"role": "system", "content": "Extract exhaustively and precisely from the provided code."},
                   {"role": "user", "content": QUESTION + "\n\nCODE:\n" + seen}], temperature=0.2, max_tokens=4000)
    b_ans = type(cb)._content(out)
    b_cov, _ = coverage(b_ans, names)
    print(f"BASELINE (1 pass{', TRUNCATED' if len(corpus) > budget else ''}; {in_view*100:.0f}% of classes physically in view): "
          f"answer_coverage={b_cov:.2f}  tokens={cb.usage.snapshot()['total_tokens']//1000}k", flush=True)

    # --- orchestrated: chunk-extractors read ALL real files ---
    cu = DeepSeekClient(model=model, max_workers=16)
    cfg = UltracodeConfig(max_children=8)
    res = research_corpus(ROOT, QUESTION, ext=".py", include_substr=tuple(f"/{s}/" for s in SUBTREES),
                          delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn, config=cfg,
                          max_chunk_lines=300, concurrency=16, synthesize=True,
                          progress=lambda m: print("  ·", m, flush=True))
    union_txt = " ".join((f.claim + " " + (f.evidence or "")) for f in res.findings)
    u_union, _ = coverage(union_txt, names)
    u_ans, _ = coverage(res.answer, names)
    print(f"ORCHESTRATED ({res.chunks_read} chunk-extractors / {res.n_files} files): "
          f"extraction_union_coverage={u_union:.2f}  answer_coverage={u_ans:.2f}  "
          f"tokens={cu.usage.snapshot()['total_tokens']//1000}k", flush=True)
    print(f"\n=== {model}: baseline_answer={b_cov:.2f}  orchestrated_answer={u_ans:.2f} "
          f"(union {u_union:.2f})  lift={u_ans-b_cov:+.2f} ===", flush=True)


if __name__ == "__main__":
    main()
