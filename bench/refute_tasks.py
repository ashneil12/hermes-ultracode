"""Claim-refutation tasks — the purest test of the adversarial layer.

Each task is code + a set of CLAIMS, some TRUE, some SUBTLY FALSE (plausible
enough that a single confident pass tends to accept them). The metric that
matters: the FALSE-CLAIM REFUTATION RATE — does adversarial, default-to-refuted,
multi-lens verification catch the lies the bare model waves through?
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Claim:
    text: str
    is_true: bool


@dataclass
class ClaimTask:
    id: str
    code: str
    claims: List[Claim] = field(default_factory=list)


_AUTH = ClaimTask(
    id="auth_claims",
    code='''import sqlite3
def get_user(db, username):
    q = "SELECT * FROM users WHERE name = '" + username + "'"
    return db.execute(q).fetchone()

ADMIN_PASSWORD = "hunter2"

def checksum(items):
    total = 0
    for i in range(len(items) + 1):
        total += items[i]
    return total

def run_cmd(user_input):
    return eval(user_input)
''',
    claims=[
        Claim("get_user is vulnerable to SQL injection via the username parameter.", True),
        Claim("Switching get_user to a parameterized query (placeholder + params) would close the injection.", True),
        Claim("checksum() works correctly for any non-empty list of numbers.", False),  # off-by-one -> IndexError
        Claim("checksum([1, 2, 3]) returns 6.", False),  # raises IndexError at i=3
        Claim("run_cmd only evaluates simple arithmetic, so it is safe.", False),  # eval = arbitrary code
        Claim("Because ADMIN_PASSWORD is a module constant and not in a database, it is not a real security issue.", False),
        Claim("The off-by-one in checksum's range causes an IndexError on the last iteration.", True),
        Claim("This code is free of remote-code-execution risk.", False),  # eval is RCE
    ],
)

_LOGIC = ClaimTask(
    id="logic_claims",
    code='''def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2]

def dedupe(xs):
    seen = set()
    out = []
    for x in xs:
        if x not in seen:
            out.append(x)
        seen.add(x)
    return out

def percent(part, whole):
    return part / whole * 100

def is_palindrome(s):
    return s == s[::-1]
''',
    claims=[
        Claim("median() returns the correct median for even-length lists.", False),  # returns upper-middle, not avg of two
        Claim("median([1, 2, 3, 4]) returns 2.5.", False),  # returns 3
        Claim("dedupe() preserves first-occurrence order and removes duplicates.", True),
        Claim("percent() raises ZeroDivisionError when whole is 0.", True),
        Claim("is_palindrome() is correct for the string 'racecar'.", True),
        Claim("median() handles an empty list gracefully.", False),  # IndexError
        Claim("dedupe() is O(n) because membership tests on a set are O(1) average.", True),
        Claim("percent(1, 3) returns exactly 33.33.", False),  # floating point, not exact
    ],
)

CLAIM_TASKS: List[ClaimTask] = [_AUTH, _LOGIC]


def totals():
    t = sum(len(c.claims) for c in CLAIM_TASKS)
    f = sum(1 for ct in CLAIM_TASKS for c in ct.claims if not c.is_true)
    return {"claims": t, "false": f, "true": t - f}
