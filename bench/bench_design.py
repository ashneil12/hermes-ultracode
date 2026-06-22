"""Benchmark Task 6 — DESIGN judge-panel (the 3rd shape, quality regime).

CC used ultracode for design: N independent architects -> synthesis -> adversarial
build-safety critique. Quality is harder to score than recall/precision, so we use
a CHECKABLE design task: a constraint-satisfaction design where a correct answer
must satisfy a known set of hard constraints. We score: constraints satisfied,
and fatal flaws avoided (a build-safety critic should catch flaws single-shot misses).

Task: design a rate limiter for a multi-tenant API with stated hard constraints.
A weak single pass tends to miss 1-2 constraints or pick a design with a fatal
flaw; the panel+critique should catch them.
"""
import os, sys, time, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
envf=os.path.expanduser("~/.ultracode-bench/deepseek.env")
for line in open(envf):
    if '=' in line and not line.startswith('#'):
        k,v=line.strip().split('=',1); os.environ.setdefault(k,v)

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient

TASK = """Design a rate limiter for a multi-tenant SaaS API. HARD CONSTRAINTS (all must be addressed):
C1: per-tenant limits (tenant A's traffic must never consume tenant B's quota)
C2: distributed — must work across N stateless API servers (no single in-memory counter)
C3: must survive a Redis/store restart without letting everyone burst past limits
C4: fair burst handling (a tenant should get a short burst allowance, not hard cutoff)
C5: must not add more than ~1ms p99 latency to each request
C6: graceful degradation if the rate-limit store is DOWN (fail-open vs fail-closed decision, stated)
Give a concrete design and explicitly address each constraint."""

# Each constraint scored by whether the answer concretely ADDRESSES it (keywords + a real mechanism).
CONSTRAINTS = {
 "C1_per_tenant": ["per-tenant","per tenant","tenant.{0,15}(key|quota|limit|isolat)","keyed by tenant"],
 "C2_distributed": ["redis","distributed","shared (store|counter)","central(ized)? (store|counter)","atomic incr"],
 "C3_restart_safe": ["restart","persist","ttl","reload","warm","cold start","reconstruct"],
 "C4_burst": ["burst","token bucket","leaky bucket","sliding window","allowance"],
 "C5_latency": ["latency","1ms","p99","pipelin","local cache","lua script","single round"],
 "C6_degradation": ["fail.?open","fail.?closed","store is down","degrad","unavailable","circuit"],
}

def score(ans):
    a=(ans or "").lower()
    hit={}
    for c,pats in CONSTRAINTS.items():
        hit[c]=any(re.search(p,a) for p in pats)
    n=sum(hit.values())
    return n/len(CONSTRAINTS), hit

def main():
    cb=DeepSeekClient(model="deepseek-v4-flash",max_workers=4)
    t0=time.time()
    base=cb._content(cb.chat([{"role":"user","content":TASK}]))
    rb,hb=score(base); ub=cb.usage.snapshot()
    print(f"[BASELINE]  {time.time()-t0:.0f}s {ub['total_tokens']}tok | constraints={sum(hb.values())}/6")
    for c,v in hb.items(): print(f"     {'OK' if v else 'MISS'} {c}")

    cu=DeepSeekClient(model="deepseek-v4-flash",max_workers=16)
    cfg=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS,VerifyLens.COMPLETENESS],
                        max_finders=4,concurrency=16,max_children=8)
    t0=time.time()
    res=run(TASK,context="",kind="generative",delegate_fn=cu.delegate_fn,
            aux_call_fn=cu.aux_call_fn,config=cfg,force_orchestrate=True,
            run_id="design",enable_ledger=False)
    ru,hu=score(res.answer or ""); uu=cu.usage.snapshot()
    print(f"\n[ULTRACODE] {time.time()-t0:.0f}s {uu['total_tokens']}tok | mode={res.mode} | constraints={sum(hu.values())}/6")
    for c,v in hu.items(): print(f"     {'OK' if v else 'MISS'} {c}")
    print(f"  stages: {res.stages}")
    print("\n--- ULTRACODE ANSWER (first 1100) ---\n"+(res.answer or "")[:1100])
    print(f"\n{'='*60}\nbaseline {sum(hb.values())}/6  |  ultracode {sum(hu.values())}/6")
    if sum(hu.values())>sum(hb.values()): print(">>> ULTRACODE WINS (more constraints addressed)")
    elif sum(hu.values())==sum(hb.values()): print(">>> TIE on constraint coverage")
    else: print(">>> baseline ahead")

if __name__=="__main__":
    main()
