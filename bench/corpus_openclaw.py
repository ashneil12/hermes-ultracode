"""Second REAL corpus (different codebase + language): openclaw TypeScript SDK.

Confirms the corpus deep-research mechanism is repo/language-agnostic. Ground truth =
every exported class/interface/type/enum name in packages/memory-host-sdk/src (grep-
derived). Baseline sees one context window; chunk-extractors read all real .ts files.

Usage: python bench/corpus_openclaw.py [model] [baseline_budget_chars]
"""

import os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.corpus import research_corpus
from bench.deepseek_client import DeepSeekClient

ROOT = "/Users/ash/Projects/openclaw/packages/memory-host-sdk"
_EXP = re.compile(r"^export (?:class|interface|type|enum|abstract class) ([A-Za-z_][A-Za-z0-9_]*)", re.M)
QUESTION = ("Enumerate every exported TypeScript type-level declaration (class, interface, type alias, or enum) "
            "defined in this SDK source. For each, give its exact name and a one-line note on what it is.")


def ground_truth():
    names = set()
    for dp, _, files in os.walk(os.path.join(ROOT, "src")):
        for fn in files:
            if fn.endswith(".ts") and not fn.endswith(".test.ts"):
                try:
                    names.update(_EXP.findall(open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()))
                except OSError:
                    pass
    return names


def coverage(text, names):
    t = (text or "").lower()
    return len({n for n in names if n.lower() in t}) / max(len(names), 1)


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 60_000
    names = ground_truth()
    files = []
    for dp, _, fs in os.walk(os.path.join(ROOT, "src")):
        for fn in sorted(fs):
            if fn.endswith(".ts") and not fn.endswith(".test.ts"):
                files.append(os.path.join(dp, fn))
    corpus = "\n\n".join(f"### {os.path.relpath(f, ROOT)}\n" + open(f, encoding="utf-8", errors="replace").read() for f in sorted(files))
    print(f"ground truth: {len(names)} exported decls; corpus: {len(files)} .ts files, {len(corpus)} chars "
          f"(~{len(corpus)//4} tokens); baseline budget {budget} chars", flush=True)

    cb = DeepSeekClient(model=model, max_workers=4)
    seen = corpus[:budget]
    out = cb.chat([{"role": "system", "content": "Extract exhaustively and precisely from the provided TypeScript."},
                   {"role": "user", "content": QUESTION + "\n\nCODE:\n" + seen}], temperature=0.2, max_tokens=4000)
    b_cov = coverage(type(cb)._content(out), names)
    print(f"BASELINE (1 pass{', TRUNCATED' if len(corpus) > budget else ''}): coverage={b_cov:.2f}  "
          f"tokens={cb.usage.snapshot()['total_tokens']//1000}k", flush=True)

    cu = DeepSeekClient(model=model, max_workers=16)
    res = research_corpus(ROOT, QUESTION, ext=".ts", include_substr=("/src/",),
                          exclude_substr=("/node_modules/", "/dist/", ".test.ts", ".spec.ts"),
                          delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn, config=UltracodeConfig(max_children=8),
                          max_chunk_lines=300, concurrency=16, synthesize=True,
                          progress=lambda m: print("  ·", m, flush=True))
    union = coverage(" ".join((f.claim + " " + (f.evidence or "")) for f in res.findings), names)
    ans = coverage(res.answer, names)
    print(f"ORCHESTRATED ({res.chunks_read} chunk-extractors / {res.n_files} files): "
          f"union={union:.2f}  answer={ans:.2f}  tokens={cu.usage.snapshot()['total_tokens']//1000}k", flush=True)
    print(f"\n=== {model} (openclaw TS): baseline={b_cov:.2f}  orchestrated={ans:.2f} (union {union:.2f})  "
          f"lift={ans-b_cov:+.2f} ===", flush=True)


if __name__ == "__main__":
    main()
