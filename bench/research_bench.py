"""Research A/B: where orchestration earns its cost on non-code tasks, and where it doesn't.

Two regimes:
  EASY (factual recall): a single strong pass already saturates recall. Run under
    DISCERNMENT (no force) — the harness should route these to solo: same recall,
    a fraction of the tokens. Orchestrating them is pure overhead (the anti-pattern).
  HARD (recall-at-scale enumeration): one answer must hold 12-23 facts; a single
    shot's attention saturates and drops a few. Decompose by sub-area, one finder
    per slice, union the facts. This is where ultracode recall should beat baseline.

We score ground-truth fact recall (matches_bug) for both, and print mode + tokens so
the overhead/benefit is visible, not asserted.
"""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient
from bench.research_tasks import RESEARCH_TASKS, HARD_RESEARCH_TASKS
from bench.scorer import matches_bug


def recall(answer: str, task):
    a = (answer or "").lower()
    found = [b.name for b in task.planted if matches_bug(a, b)]
    return len(found) / len(task.planted), [b.name for b in task.planted if b.name not in found]


def baseline(model, prompt):
    cb = DeepSeekClient(model=model, max_workers=8)
    out = cb.chat([{"role": "system", "content": "Answer thoroughly, accurately, and completely."},
                   {"role": "user", "content": prompt}], temperature=0.3, max_tokens=4000)
    return type(cb)._content(out), cb.usage.snapshot()["total_tokens"]


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.COMPLETENESS],
                          max_finders=6, concurrency=12, max_children=8)

    def trial(tasks, *, force):
        brs, urs = [], []
        for t in tasks:
            b_ans, b_tok = baseline(model, t.prompt)
            b_rec, b_missed = recall(b_ans, t)
            brs.append(b_rec)
            cu = DeepSeekClient(model=model, max_workers=12)
            t0 = time.time()
            res = run(t.prompt, kind="research", force_orchestrate=force, delegate_fn=cu.delegate_fn,
                      aux_call_fn=cu.aux_call_fn, config=cfg, enable_ledger=False, run_id=t.id)
            u_rec, u_missed = recall(res.answer, t)
            urs.append(u_rec)
            u_tok = cu.usage.snapshot()["total_tokens"]
            mult = f"{u_tok/max(b_tok,1):.1f}x" if b_tok else "?"
            print(f"  {t.id:14} n={len(t.planted):2}  base={b_rec:.2f}({b_tok//1000}k)  "
                  f"ultra={u_rec:.2f}({u_tok//1000}k,{mult}) [{res.mode}, {time.time()-t0:.0f}s]  "
                  f"u_missed={u_missed}", flush=True)
        return sum(brs)/len(brs), sum(urs)/len(urs)

    print(f"\n### EASY (factual recall, DISCERNMENT on — should route to solo, no recall gain expected)")
    eb, eu = trial(RESEARCH_TASKS, force=None)
    print(f"  >>> EASY mean: baseline={eb:.3f}  ultracode={eu:.3f}")

    print(f"\n### HARD (recall-at-scale enumeration, orchestration forced — decomposition should LIFT recall)")
    hb, hu = trial(HARD_RESEARCH_TASKS, force=True)
    print(f"  >>> HARD mean: baseline={hb:.3f}  ultracode={hu:.3f}  (lift={hu-hb:+.3f})", flush=True)


if __name__ == "__main__":
    main()
