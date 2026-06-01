"""Live smoke test: run the ultracode harness against real deepseek-v4-pro."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient

CODE = '''
# auth.py
import sqlite3
def get_user(db, username):
    q = "SELECT * FROM users WHERE name = '" + username + "'"   # (1) SQL injection
    return db.execute(q).fetchone()

ADMIN_PASSWORD = "hunter2"                                       # (2) hardcoded secret

def checksum(items):
    total = 0
    for i in range(len(items) + 1):                             # (3) off-by-one: IndexError
        total += items[i]
    return total

def run_cmd(user_input):
    return eval(user_input)                                      # (4) eval of user input (RCE)
'''

def main():
    client = DeepSeekClient(model="deepseek-v4-pro", max_workers=6)
    cfg = UltracodeConfig(
        verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES],
        max_finders=4, max_children=6, discovery_dry_rounds=2, discovery_max_rounds=4,
    )
    t0 = time.time()
    res = run(
        "Find ALL security and correctness bugs in this Python code.",
        context=CODE,
        delegate_fn=client.delegate_fn,
        aux_call_fn=client.aux_call_fn,
        config=cfg,
        force_orchestrate=True,
        enable_ledger=True,
        run_id="smoke",
    )
    dt = time.time() - t0
    print(f"\n=== MODE: {res.mode}  ({dt:.1f}s) ===")
    print("decision:", res.decision.reason)
    if res.plan:
        print("plan rationale:", res.plan.rationale)
        for st in res.plan.subtasks:
            print("  subtask:", st.goal[:90])
    print(f"\n=== FINDINGS ({len(res.findings)}) ===")
    for f in res.findings:
        votes = "".join("C" if v.verdict.value == "confirmed" else ("R" if v.verdict.value == "refuted" else "P") for v in f.votes)
        print(f"  [{'SURVIVED' if f.survived else 'killed  '}] {f.severity:8} {f.claim[:70]:70} @{f.locator[:18]:18} votes={votes}")
    print(f"\n=== SURVIVORS ({len(res.survivors)}) ===")
    for f in res.survivors:
        print(f"  - {f.claim[:80]} @{f.locator}")
    print(f"\n=== CAPS ANNOUNCED ===")
    for c in res.caps_announced:
        print("  -", c)
    print(f"\n=== ANSWER ===\n{res.answer[:1200]}")
    print(f"\n=== USAGE === {client.usage.snapshot()}")

if __name__ == "__main__":
    main()
