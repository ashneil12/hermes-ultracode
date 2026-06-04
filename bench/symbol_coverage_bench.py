"""Symbol coverage over a real codebase — the 'find every function/class in this repo' task.

This is the agent use case that motivates orchestration: "list every endpoint", "find all callers",
"audit every handler". Per-symbol recognition is trivial; COVERAGE across a repo bigger than one pass
is the whole job. Corpus = a directory of Python source; GOLD = every top-level def/class name, taken
exactly from the AST (no judge). Bounded reads one working set; ultracode uses the harness
enumerate_corpus primitive (chunk per file -> fan-out -> union). recall = symbols found / all symbols.

  python bench/symbol_coverage_bench.py single_budget deepseek-v4-flash [path]
  python bench/symbol_coverage_bench.py ultracode      deepseek-v4-flash [path]
"""

import ast
import glob
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultracode.config import UltracodeConfig
from ultracode.corpus import enumerate_corpus
from bench.ner_coverage_bench import _truncated
from bench.deepseek_client import DeepSeekClient

RES = Path(__file__).resolve().parent / "results"
DEFAULT_PATH = str(Path(__file__).resolve().parents[1] / "agent" / "ultracode")
BUDGET_CHARS = 24000
INSTR = "function or class name DEFINED in the code (every def and class)"


def load(path):
    files = sorted(glob.glob(os.path.join(path, "*.py")))
    docs, gold = [], set()
    for f in files:
        src = open(f).read()
        docs.append((os.path.basename(f), src))
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                gold.add(n.name)
    return docs, gold


def recall(items_text, gold):
    found = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", items_text or ""))
    hit = sum(1 for g in gold if g in found)
    return hit / max(len(gold), 1)


def run_single(client, docs, budget):
    corpus = "\n\n".join(f"### {name}\n{src}" for name, src in docs)[:budget]
    msgs = [{"role": "system", "content": "You are a precise code analyst. List every function and class "
             "DEFINED in the code, exhaustively, one name per line. Never summarize."},
            {"role": "user", "content": f"List every {INSTR}, one name per line:\n\n{corpus}"}]
    mt, ans = 8000, ""
    for _ in range(4):
        resp = client.chat(msgs, temperature=0.1, max_tokens=mt)
        ans = type(client)._content(resp)
        if ans.strip() and not _truncated(resp):
            return ans
        mt *= 2
    return ans


def run_ultra(model, docs, cfg):
    cu = DeepSeekClient(model=model, max_workers=6)
    sections = [f"### {name}\n{src}" for name, src in docs]   # one section per file
    res = enumerate_corpus(sections, INSTR, delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn,
                           config=cfg, concurrency=6, retry_empty=3, single_pass_chars=0)
    return " \n ".join(res.items)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single_budget"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    path = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_PATH
    RES.mkdir(exist_ok=True)
    docs, gold = load(path)
    total_chars = sum(len(s) for _, s in docs)
    cfg = UltracodeConfig(max_children=6, concurrency=6)
    print(f"\n=== symbol coverage — {mode} {model} ({len(docs)} files, {total_chars//1000}k chars, "
          f"{len(gold)} symbols) ===\n", flush=True)
    t0 = time.time()
    if mode == "single_budget":
        ans = run_single(DeepSeekClient(model=model, max_workers=4), docs, BUDGET_CHARS)
    else:
        ans = run_ultra(model, docs, cfg)
    r = recall(ans, gold)
    print(f"  recall = {r:.3f} ({int(r*len(gold))}/{len(gold)} symbols)  [{time.time()-t0:.0f}s]", flush=True)
    import json
    (RES / f"symbol_{mode}_{model}.json").write_text(json.dumps({"recall": round(r, 3), "gold": len(gold),
                                                                 "chars": total_chars}))


if __name__ == "__main__":
    main()
