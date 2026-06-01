"""Demonstrate the harness on NON-code tasks (research, generative)."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient


def demo(label, task, kind, *, context="", force=True):
    c = DeepSeekClient(model="deepseek-v4-flash", max_workers=16)
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.COMPLETENESS],
                          max_finders=4, concurrency=16, max_children=8)
    t0 = time.time()
    res = run(task, context=context, kind=kind, delegate_fn=c.delegate_fn, aux_call_fn=c.aux_call_fn,
              config=cfg, force_orchestrate=force, run_id=label, enable_ledger=False)
    u = c.usage.snapshot()
    print(f"\n{'='*90}\n### {label}: mode={res.mode} kind={kind}  ({time.time()-t0:.0f}s, {u['total_tokens']}tok)", flush=True)
    print("stages:", res.stages, flush=True)
    if res.findings:
        print(f"findings ({len(res.survivors)} survived of {len(res.findings)}):", flush=True)
        for f in res.survivors[:8]:
            print(f"  - [{f.verdict.value if f.verdict else '?'}] {f.claim[:100]}", flush=True)
    print("\nANSWER:\n" + (res.answer or "")[:1400], flush=True)


if __name__ == "__main__":
    demo("RESEARCH", "What are the key technical differences between HTTP/1.1, HTTP/2, and HTTP/3, and what specific problem does each generation solve?", "research")
    demo("GENERATIVE", "Write a punchy one-line tagline for an open-source, self-hostable AI coding agent that runs anywhere.", "generative")
    demo("ANALYSIS", "Analyze the tradeoffs of using SQLite vs PostgreSQL for a small-to-medium SaaS backend.", "analysis")
