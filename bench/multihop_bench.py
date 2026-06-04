"""Real multi-hop QA (HotpotQA) under the same bounded-pass regime as longctx_bench.

HotpotQA is a recognized, cited multi-hop benchmark: each question needs facts chained across 2 gold
Wikipedia paragraphs, hidden among distractors. In the standard distractor setting (10 paragraphs) the
evidence fits one pass — so we reproduce the *fullwiki* reality: bury the 2 gold paragraphs in a larger
haystack of K distractors drawn from a shared pool. Now a single bounded pass can only see a working
set's worth (the gold may fall outside it), while ultracode chunks the whole haystack, fans out one
reader per section, and synthesizes the multi-hop answer from the union. Scored with the official
HotpotQA answer F1 / EM (SQuAD normalization). Same regime, real data.

  python bench/multihop_bench.py single_budget deepseek-v4-flash    # bounded one pass
  python bench/multihop_bench.py ultracode      deepseek-v4-flash    # chunk -> fan-out -> synthesize
"""

import json
import random
import re
import string
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultracode.config import UltracodeConfig
from ultracode.corpus import research_corpus
from bench.deepseek_client import DeepSeekClient

DATA = Path(__file__).resolve().parent / "data" / "hotpot_dev_200.json"
RES = Path(__file__).resolve().parent / "results"
N_EVAL = 20                  # questions evaluated
KS = [8, 60]                 # distractor paragraphs around the 2 gold (context-pressure axis)
BUDGET_CHARS = 24000         # the bounded single-pass working set (~6k tokens)
PARAS_PER_FILE = 5


# ---- official HotpotQA / SQuAD answer scoring ----
def _norm(s):
    s = s.lower()
    s = "".join(ch for ch in s if ch not in string.punctuation)
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def f1(pred, gold):
    p, g = _norm(pred).split(), _norm(gold).split()
    if not p or not g:
        return float(p == g)
    same = sum((Counter(p) & Counter(g)).values())
    if not same:
        return 0.0
    prec, rec = same / len(p), same / len(g)
    return 2 * prec * rec / (prec + rec)


def em(pred, gold):
    return float(_norm(pred) == _norm(gold))


def _answer(text):
    # the solvers end with 'ANSWER: <span>'; fall back to last non-empty line
    m = re.findall(r"ANSWER:\s*(.+)", text or "", re.I)
    if m:
        return m[-1].strip()
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return lines[-1] if lines else ""


def build_haystack(item, pool, k, seed):
    gold = [p for p in item["paras"] if p["title"] in item["gold_titles"]]
    distractors = [p for p in pool if p["title"] not in item["gold_titles"]]
    rng = random.Random(seed)
    picked = rng.sample(distractors, min(k, len(distractors)))
    hay = gold + picked
    rng.shuffle(hay)            # gold is buried at a random depth
    return hay, len(gold)


def solve_single(client, question, hay, budget):
    corpus = "\n\n".join(f"== {p['title']} ==\n{p['text']}" for p in hay)
    if len(corpus) > budget:
        corpus = corpus[:budget]
    out = client.chat(
        [{"role": "system", "content": "Answer the multi-hop question using ONLY the paragraphs. "
          "Chain facts across paragraphs as needed. Reply with just the short answer, ending with a "
          "line 'ANSWER: <answer>' (a short phrase, entity, number, or yes/no)."},
         {"role": "user", "content": f"QUESTION: {question}\n\n=== PARAGRAPHS ===\n{corpus}"}],
        temperature=0.1, max_tokens=1500)
    return _answer(type(client)._content(out))


def solve_ultra(model, question, hay, cfg):
    cu = DeepSeekClient(model=model, max_workers=16)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for i in range(0, len(hay), PARAS_PER_FILE):
            body = "\n\n".join(f"== {p['title']} ==\n{p['text']}" for p in hay[i:i + PARAS_PER_FILE])
            (root / f"sec_{i // PARAS_PER_FILE:03d}.txt").write_text(body)
        res = research_corpus(
            str(root), question, ext=(".txt",), delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn,
            config=cfg, concurrency=16, max_chunk_lines=400, synthesize=False, verify=False)
        facts = "\n".join(f"- {f.claim} ({f.evidence})" for f in res.findings[:60]) or "(no facts found)"
    # synthesize the multi-hop answer from the reconciled facts
    msg = [{"role": "system", "content": "Answer the multi-hop question by chaining the extracted facts. "
            "Reply with just the short answer, ending 'ANSWER: <answer>'."},
           {"role": "user", "content": f"QUESTION: {question}\n\nFACTS EXTRACTED FROM THE CORPUS:\n{facts}"}]
    return _answer(type(cu)._content(cu.chat(msg, temperature=0.1, max_tokens=1500))), len(res.findings)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single_budget"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    RES.mkdir(exist_ok=True)
    rows = json.loads(DATA.read_text())
    pool = [p for r in rows for p in r["paras"]]
    items = rows[:N_EVAL]
    cfg = UltracodeConfig(concurrency=16, max_children=16, reconcile=True)
    print(f"\n=== HotpotQA multi-hop (bounded-pass regime) — {mode} {model} "
          f"(n={N_EVAL}, pool={len(pool)} paras) ===\n")
    out = {}
    for k in KS:
        f1s, ems = [], []
        t0 = time.time()
        for qi, item in enumerate(items):
            hay, _ = build_haystack(item, pool, k, seed=7000 + qi)
            try:
                if mode == "single_budget":
                    cb = DeepSeekClient(model=model, max_workers=4)
                    pred = solve_single(cb, item["question"], hay, BUDGET_CHARS)
                else:
                    pred, _ = solve_ultra(model, item["question"], hay, cfg)
            except Exception:
                pred = ""
            f1s.append(f1(pred, item["answer"]))
            ems.append(em(pred, item["answer"]))
        mf1, mem = sum(f1s) / len(f1s), sum(ems) / len(ems)
        approx_chars = sum(len(p["text"]) for p in build_haystack(items[0], pool, k, 7000)[0])
        out[str(k)] = {"f1": round(mf1, 3), "em": round(mem, 3), "k": k}
        print(f"  K={k:3d} distractors (~{approx_chars//1000}k chars/q)  "
              f"F1={mf1:.3f}  EM={mem:.3f}   [{time.time()-t0:.0f}s]", flush=True)
    (RES / f"multihop_{mode}_{model}.json").write_text(json.dumps({"n": N_EVAL, "by_k": out}, indent=1))
    print(f"\n  saved -> results/multihop_{mode}_{model}.json")


if __name__ == "__main__":
    main()
