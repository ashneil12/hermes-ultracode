"""Benchmark Task 2 — PRECISION regime (the win case for ultracode).

A corpus with REAL planted bugs + bug-shaped DECOYS (benign code that pattern-
matches as buggy). Baseline single-pass tends to over-flag the decoys (low
precision). The harness's adversarial verify (default-to-refuted, mechanism
required) should KILL the decoys, lifting precision while holding recall.

Scored: recall (real bugs found / total real), precision (real / all claimed).
This is the regime the user's ULTRACODE_REPORT proved ultracode wins.
"""
import os, sys, time, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

envf = os.path.expanduser("~/.ultracode-bench/deepseek.env")
if os.path.exists(envf):
    for line in open(envf):
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from ultracode.steering import decide
from bench.deepseek_client import DeepSeekClient

# Corpus: a small auth/session service. REAL bugs marked R#, DECOYS marked D#.
CORPUS = r'''
# ===== file: auth.py =====
import jwt, hashlib, hmac, time

SECRET = os.environ["JWT_SECRET"]

def make_token(user_id):
    # R1: HS256 token signed but exp is set in SECONDS-from-now added to ms timestamp -> never expires correctly
    payload = {"uid": user_id, "exp": int(time.time() * 1000) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(tok):
    # R2: verify=False disables signature check entirely -> forgeable tokens
    return jwt.decode(tok, SECRET, algorithms=["HS256"], options={"verify_signature": False})

def constant_time_eq(a, b):
    # D1 (DECOY): looks like a timing bug but uses hmac.compare_digest -> actually SAFE
    return hmac.compare_digest(a.encode(), b.encode())

# ===== file: users.py =====
def get_user(db, uid):
    # D2 (DECOY): looks like SQL injection but uses a parameterized query -> SAFE
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

def update_role(db, request, target_uid, new_role):
    # R3: no authorization check — any caller can set any user's role (IDOR/privilege escalation)
    db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_uid))
    db.commit()

def hash_password(pw):
    # D3 (DECOY): sha256 without salt LOOKS weak, but this codebase only uses it for
    # a non-security cache key (see comment) -> not a real auth vuln in context
    return hashlib.sha256(pw.encode()).hexdigest()  # cache key only, not credential storage

# ===== file: session.py =====
SESSIONS = {}

def create_session(uid):
    # R4: session id is predictable (sequential counter) -> session prediction/hijack
    sid = len(SESSIONS) + 1
    SESSIONS[sid] = uid
    return sid

def get_session(sid):
    # D4 (DECOY): missing None-check looks like a crash bug, but caller always guards -> benign
    return SESSIONS[sid]
'''

REAL_BUGS = {
    "R1": ["exp", "expir", "timestamp", "* 1000", "milli"],
    "R2": ["verify_signature", "verify=False", "signature"],
    "R3": ["authoriz", "role", "IDOR", "privilege", "access control"],
    "R4": ["predictable", "sequential", "session id", "counter", "hijack"],
}
DECOYS = {
    "D1": ["compare_digest", "constant_time", "timing"],
    "D2": ["sql inject", "parameteriz"],
    "D3": ["salt", "sha256"],
    "D4": ["none", "null", "keyerror", "crash"],
}

def score(answer):
    a = (answer or "").lower()
    # recall: a real bug counts found if any of its keyword signatures appears in a CLAIM
    found_real = sum(1 for b, kws in REAL_BUGS.items() if any(k.lower() in a for k in kws))
    recall = found_real / len(REAL_BUGS)
    # false positives: a decoy counts as wrongly-flagged if it's asserted as a vuln
    fp = sum(1 for d, kws in DECOYS.items() if any(k.lower() in a for k in kws))
    claimed = found_real + fp
    precision = (found_real / claimed) if claimed else 0.0
    return recall, precision, found_real, fp

def main():
    task = ("Audit this auth/session service for SECURITY vulnerabilities. Report ONLY "
            "genuine, exploitable vulnerabilities with a stated mechanism. Do not flag "
            "code that looks risky but is actually safe in context.")
    d = decide(task)
    print(f"gate: orchestrate={d.orchestrate} shape={d.shape.value} lenses={[l.value for l in d.lenses]}\n")

    cb = DeepSeekClient(model="deepseek-v4-flash", max_workers=4)
    t0 = time.time()
    base = cb._content(cb.chat([{"role":"user","content": task + "\n\nCODE:\n" + CORPUS}]))
    rb, pb, frb, fpb = score(base)
    ub = cb.usage.snapshot()
    print(f"[BASELINE]  {time.time()-t0:.0f}s {ub['total_tokens']}tok | recall={rb:.2f} precision={pb:.2f} (real={frb}/4, FP={fpb}/4)")

    cu = DeepSeekClient(model="deepseek-v4-flash", max_workers=16)
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY],
                          max_finders=4, concurrency=16, max_children=8, verify_rounds=2)
    t0 = time.time()
    res = run(task, context=CORPUS, kind="audit", delegate_fn=cu.delegate_fn,
              aux_call_fn=cu.aux_call_fn, config=cfg, force_orchestrate=True,
              run_id="precision", enable_ledger=False)
    ru, pu, fru, fpu = score(res.answer or "")
    uu = cu.usage.snapshot()
    print(f"[ULTRACODE] {time.time()-t0:.0f}s {uu['total_tokens']}tok | recall={ru:.2f} precision={pu:.2f} (real={fru}/4, FP={fpu}/4)")
    print(f"  stages: {res.stages} | findings {len(res.survivors)} survived of {len(res.findings)}")
    print("\n--- ULTRACODE ANSWER (first 1400) ---\n" + (res.answer or "")[:1400])
    print(f"\n{'='*70}\nSCORE  baseline: R={rb:.2f} P={pb:.2f}  |  ultracode: R={ru:.2f} P={pu:.2f}")
    print("WIN" if (pu > pb and ru >= rb - 0.001) else "no precision gain")

if __name__ == "__main__":
    main()
