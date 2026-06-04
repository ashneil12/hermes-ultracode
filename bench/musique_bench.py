"""MuSiQue multi-hop QA under the bounded-pass regime — the *anti-shortcut* real dataset.

MuSiQue questions are COMPOSED ("the spouse of the Green performer", "who founded the company that
distributed UHF") so a model can't answer from memorized facts — it must chain the evidence. That makes
it the clean real-data test of the bottleneck thesis: if HotpotQA washed out for Opus because Opus
*memorized* the answers, MuSiQue should remove that shortcut, so burying the evidence should hurt even a
frontier model — and orchestration should recover it. Same setup as multihop_bench: bury the ~2 gold
paragraphs among K distractors from a shared pool; score with alias-aware answer F1/EM.

  python bench/musique_bench.py single_budget deepseek-v4-flash
  python bench/musique_bench.py ultracode      deepseek-v4-flash
"""

import json
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
from bench.multihop_bench import f1 as _f1, em as _em, _answer, BUDGET_CHARS

DATA = Path(__file__).resolve().parent / "data" / "musique_dev_200.json"
RES = Path(__file__).resolve().parent / "results"
N_EVAL = 20
KS = [8, 120]                # deeper burial than HotpotQA: MuSiQue paras are short, gold must clear ~24k
PARAS_PER_FILE = 6


def f1_alias(pred, item):
    return max(_f1(pred, c) for c in [item["answer"], *item.get("aliases", [])] or [item["answer"]])


def em_alias(pred, item):
    return max(_em(pred, c) for c in [item["answer"], *item.get("aliases", [])] or [item["answer"]])


def build_haystack(item, pool, k, seed):
    gold = [p for p in item["paras"] if p["title"] in item["gold_titles"]]
    distractors = [p for p in pool if p["title"] not in item["gold_titles"]]
    rng = random.Random(seed)
    hay = gold + rng.sample(distractors, min(k, len(distractors)))
    rng.shuffle(hay)
    return hay


def solve_single(client, question, hay, budget):
    corpus = "\n\n".join(f"== {p['title']} ==\n{p['text']}" for p in hay)[:budget]
    out = client.chat(
        [{"role": "system", "content": "Answer the multi-hop question using ONLY the paragraphs. "
          "Chain facts across paragraphs as needed. Reply with just the short answer, ending with a "
          "line 'ANSWER: <answer>'."},
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
    msg = [{"role": "system", "content": "Answer the multi-hop question by chaining the extracted facts. "
            "Reply with just the short answer, ending 'ANSWER: <answer>'."},
           {"role": "user", "content": f"QUESTION: {question}\n\nFACTS EXTRACTED FROM THE CORPUS:\n{facts}"}]
    return _answer(type(cu)._content(cu.chat(msg, temperature=0.1, max_tokens=1500)))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single_budget"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    RES.mkdir(exist_ok=True)
    rows = json.loads(DATA.read_text())
    pool = [p for r in rows for p in r["paras"]]
    items = rows[:N_EVAL]
    cfg = UltracodeConfig(concurrency=16, max_children=16, reconcile=True)
    print(f"\n=== MuSiQue multi-hop (bounded-pass regime) — {mode} {model} "
          f"(n={N_EVAL}, 2-hop composed, pool={len(pool)}) ===\n")
    out_path = RES / f"musique_{mode}_{model}.json"
    out = {}
    for k in KS:
        f1s, ems = [], []
        t0 = time.time()
        for qi, item in enumerate(items):
            try:
                hay = build_haystack(item, pool, k, seed=9000 + qi)
                if mode == "single_budget":
                    cb = DeepSeekClient(model=model, max_workers=4)
                    pred = solve_single(cb, item["question"], hay, BUDGET_CHARS)
                else:
                    pred = solve_ultra(model, item["question"], hay, cfg)
                f1s.append(f1_alias(pred, item)); ems.append(em_alias(pred, item))
            except Exception as e:
                print(f"    q{qi} K={k} error: {type(e).__name__}: {e}", flush=True)
                f1s.append(0.0); ems.append(0.0)
        mf1, mem = sum(f1s) / len(f1s), sum(ems) / len(ems)
        approx = sum(len(p["text"]) for p in build_haystack(items[0], pool, k, 9000))
        out[str(k)] = {"f1": round(mf1, 3), "em": round(mem, 3), "k": k}
        out_path.write_text(json.dumps({"n": N_EVAL, "by_k": out}, indent=1))  # checkpoint per K
        print(f"  K={k:3d} distractors (~{approx//1000}k chars/q)  F1={mf1:.3f}  EM={mem:.3f}  "
              f"[{time.time()-t0:.0f}s]", flush=True)
    print(f"\n  saved -> {out_path.name}")


if __name__ == "__main__":
    main()
