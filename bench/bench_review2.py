"""Benchmark Task 4 — adversarial REVIEW, SUBTLE decoys (precision win regime).

My first precision test failed to separate the two because the decoys were too
obvious. This version plants bugs that require DATA-FLOW tracing across functions
(the thing ULTRACODE_REPORT said baseline pattern-matches and gets wrong), plus
decoys that look buggy locally but are safe given cross-function context.

If the harness's adversarial verify (default-to-refuted, mechanism-required,
2 rounds) lifts precision over baseline here, that's the second-shape win.
"""
import os, sys, time, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

envf = os.path.expanduser("~/.ultracode-bench/deepseek.env")
if os.path.exists(envf):
    for line in open(envf):
        line=line.strip()
        if line and "=" in line and not line.startswith("#"):
            k,v=line.split("=",1); os.environ.setdefault(k,v)

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient

# Subtle cross-function bugs (R) + cross-function-safe decoys (D).
CORPUS = r'''
# ===== file: cache.py =====
_cache = {}
def cache_key(user, resource):
    # D1: looks like weak hashing (no crypto) but it's only a dict key, never a token. SAFE.
    return f"{user}:{resource}"

def get_cached(user, resource, ttl=300):
    k = cache_key(user, resource)
    entry = _cache.get(k)
    if entry and (time.time() - entry["t"]) < ttl:
        return entry["v"]
    return None

# ===== file: payments.py =====
def charge(account, amount_cents):
    # R1: amount validated as > 0 here, but refund() below reuses the SAME path with a
    # negative amount and NO re-validation -> a refund can be turned into a charge-credit loop.
    if amount_cents <= 0:
        raise ValueError("amount must be positive")
    account.balance -= amount_cents
    return True

def refund(account, amount_cents):
    # R1 sink: calls the ledger write directly, bypassing charge()'s validation.
    account.balance += amount_cents   # no check that amount_cents matches an actual prior charge
    ledger_write(account, -amount_cents)

def apply_discount(price, pct):
    # D2: pct could be >100 in theory, but the only caller clamps pct to [0,80] (see checkout). SAFE.
    return int(price * (1 - pct/100))

# ===== file: checkout.py =====
def checkout(cart, account, discount_pct):
    pct = max(0, min(80, discount_pct))   # clamp — this is why apply_discount D2 is safe
    total = sum(apply_discount(i.price, pct) for i in cart.items)
    # R2: total can be 0 if cart is empty, and charge() raises on amount<=0, so an empty
    # cart 500s instead of being rejected gracefully -> DoS-ish, but the REAL bug is below:
    # R3: account fetched by client-supplied id with no ownership check (IDOR on payment).
    return charge(account, total)

# ===== file: auth.py =====
def current_user(session):
    # D3: returns None if no session — looks like a missing-auth bug, but every caller is
    # behind @login_required (decorator not shown) so None never reaches sensitive code. SAFE.
    return session.get("uid")
'''

REAL = {
    "R1": ["refund", "re-validat", "bypass", "negative", "no check", "without validat", "reuse"],
    "R2": ["empty cart", "total 0", "total can be 0", "amount<=0", "zero total"],
    "R3": ["ownership", "idor", "client-supplied", "no ownership", "authoriz", "access control"],
}
DECOYS = {
    "D1": ["weak hash", "cache_key", "insecure hash", "md5", "predictable key"],
    "D2": ["discount", "pct > 100", "over 100", "apply_discount"],
    "D3": ["current_user returns none", "missing auth", "none check", "current_user"],
}

def score(ans):
    a=(ans or "").lower()
    real=sum(1 for kws in REAL.values() if any(k in a for k in kws))
    fp=sum(1 for kws in DECOYS.values() if any(k in a for k in kws))
    recall=real/len(REAL)
    prec=real/(real+fp) if (real+fp) else 0.0
    return recall,prec,real,fp

def main():
    task=("Review this payment/checkout code for genuine, exploitable bugs. Report ONLY "
          "real bugs with a stated mechanism and exploitation path. Trace data flow across "
          "functions — do not flag code that is safe given how its callers use it.")
    cb=DeepSeekClient(model="deepseek-v4-flash",max_workers=4)
    t0=time.time()
    base=cb._content(cb.chat([{"role":"user","content":task+"\n\nCODE:\n"+CORPUS}]))
    rb,pb,frb,fpb=score(base); ub=cb.usage.snapshot()
    print(f"[BASELINE]  {time.time()-t0:.0f}s {ub['total_tokens']}tok | R={rb:.2f} P={pb:.2f} (real={frb}/3 FP={fpb}/3)")

    cu=DeepSeekClient(model="deepseek-v4-flash",max_workers=16)
    cfg=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS,VerifyLens.SECURITY],
                        max_finders=4,concurrency=16,max_children=8,verify_rounds=2,
                        verify_default_refuted=True)
    t0=time.time()
    res=run(task,context=CORPUS,kind="code",delegate_fn=cu.delegate_fn,
            aux_call_fn=cu.aux_call_fn,config=cfg,force_orchestrate=True,
            run_id="review2",enable_ledger=False)
    ru,pu,fru,fpu=score(res.answer or ""); uu=cu.usage.snapshot()
    print(f"[ULTRACODE] {time.time()-t0:.0f}s {uu['total_tokens']}tok | R={ru:.2f} P={pu:.2f} (real={fru}/3 FP={fpu}/3)")
    print(f"  stages: {res.stages} | {len(res.survivors)} survived of {len(res.findings)}")
    print("\n--- ULTRACODE ANSWER (first 1200) ---\n"+(res.answer or "")[:1200])
    print(f"\n{'='*70}\nbaseline R={rb:.2f} P={pb:.2f}  |  ultracode R={ru:.2f} P={pu:.2f}")
    if pu>pb+0.05 and ru>=rb-0.001: print(">>> ULTRACODE WINS (precision up, recall held)")
    elif ru>rb+0.05: print(">>> ULTRACODE WINS (recall up)")
    elif abs(pu-pb)<=0.05 and abs(ru-rb)<=0.05: print(">>> TIE")
    else: print(">>> baseline ahead")

if __name__=="__main__":
    main()
