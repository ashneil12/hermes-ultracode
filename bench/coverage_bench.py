"""Deep-research COVERAGE A/B: does facet-decomposed orchestration cover more of a
broad question's rubric than a single shot?

This is the regime where orchestration SHOULD win (unlike trivial recall, which a
single pass saturates): a broad question has a long tail of sub-points that one pass's
attention drops, but per-facet deep dives + landscape synthesis recover. Metric =
fraction of rubric points present in the SYNTHESIZED answer (depth that survives to
the reader). Scored deterministically with scorer.matches_bug (concept+mechanism
keywords, so a bare name-drop doesn't count).

Usage: python bench/coverage_bench.py [model] [seeds]
"""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.coverage_tasks import COVERAGE_TASKS
from bench.deepseek_client import DeepSeekClient
from bench.research_bench import baseline
from bench.scorer import matches_bug


def coverage(answer: str, task):
    a = (answer or "").lower()
    found = [r.name for r in task.planted if matches_bug(a, r)]
    missed = [r.name for r in task.planted if r.name not in found]
    return len(found) / len(task.planted), found, missed


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.COMPLETENESS],
                          max_finders=6, concurrency=12, max_children=8)
    b_means, u_means = [], []
    for t in COVERAGE_TASKS:
        brec, urec, utok_ratio, umode, umissed_last = [], [], [], "", []
        for s in range(seeds):
            b_ans, b_tok = baseline(model, t.prompt)
            bc, _, _ = coverage(b_ans, t)
            brec.append(bc)
            cu = DeepSeekClient(model=model, max_workers=12)
            t0 = time.time()
            res = run(t.prompt, kind="research", force_orchestrate=True, delegate_fn=cu.delegate_fn,
                      aux_call_fn=cu.aux_call_fn, config=cfg, enable_ledger=False, run_id=f"{t.id}-s{s}")
            uc, ufound, umissed = coverage(res.answer, t)
            urec.append(uc)
            u_tok = cu.usage.snapshot()["total_tokens"]
            utok_ratio.append(u_tok / max(b_tok, 1)); umode = res.mode; umissed_last = umissed
            dt = time.time() - t0
            print(f"  {t.id:13} s{s}  base_cov={bc:.2f}  ultra_cov={uc:.2f} "
                  f"[{umode}, {dt:.0f}s, {u_tok//1000}k, {u_tok/max(b_tok,1):.0f}x]", flush=True)
        bm, um = sum(brec)/len(brec), sum(urec)/len(urec)
        b_means.append(bm); u_means.append(um)
        print(f"  >>> {t.id:13} n_rubric={len(t.planted):2}  base={bm:.2f}  ultra={um:.2f}  "
              f"lift={um-bm:+.2f}  ultra_missed={umissed_last}  facets={len(t.facets)}", flush=True)
    B, U = sum(b_means)/len(b_means), sum(u_means)/len(u_means)
    print(f"\n=== {model} (seeds={seeds}): mean baseline coverage={B:.3f}  "
          f"mean ultracode coverage={U:.3f}  (lift={U-B:+.3f}) ===", flush=True)


if __name__ == "__main__":
    main()
