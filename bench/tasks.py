"""Benchmark tasks with OBJECTIVE ground truth.

Each task is a code sample with PLANTED bugs whose signatures we know, so recall
and precision are auto-scorable (no LLM judge in the loop — the scoring must be
trustworthy). A bug is "found" if some finding's text contains all keywords of
any of its signature variants. We also include near-clean samples to measure the
false-positive rate — the thing adversarial verification is supposed to control.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Bug:
    name: str
    severity: str
    # a bug is matched if ANY variant's keywords are ALL present in a finding's text
    signatures: List[List[str]]


@dataclass
class BugTask:
    id: str
    prompt: str
    code: str
    planted: List[Bug] = field(default_factory=list)
    # how many *spurious* findings we tolerate before precision suffers (informational)
    near_clean: bool = False
    # informational: the facet decomposition a comprehensive answer should cover (printed, not scored)
    facets: List[str] = field(default_factory=list)


_AUTH = BugTask(
    id="auth",
    prompt="Find ALL security and correctness bugs in this Python code.",
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
    planted=[
        Bug("sql_injection", "critical", [["sql", "inject"], ["unsanit", "query"], ["string", "concat", "query"]]),
        Bug("hardcoded_secret", "high", [["hardcod", "password"], ["hardcod", "secret"], ["plaintext", "password"]]),
        Bug("off_by_one", "high", [["off-by-one"], ["off by one"], ["index", "out of range"], ["len(items) + 1"], ["indexerror"]]),
        Bug("eval_rce", "critical", [["eval"], ["arbitrary code"], ["code injection"], ["rce"]]),
    ],
)

_FILEOPS = BugTask(
    id="fileops",
    prompt="Find ALL bugs (security, resource, and error-handling) in this code.",
    code='''import os

def read_user_file(base, name):
    path = base + "/" + name
    f = open(path)
    data = f.read()
    return data

def save(path, data):
    try:
        with open(path, "w") as f:
            f.write(data)
    except:
        pass

def cleanup(paths):
    for p in paths:
        os.system("rm -rf " + p)
''',
    planted=[
        Bug("path_traversal", "high", [["path", "travers"], ["directory", "travers"], ["../"], ["sanitiz", "path"]]),
        Bug("resource_leak", "medium", [["not", "close"], ["file", "leak"], ["unclosed"], ["resource", "leak"], ["close", "file"]]),
        Bug("bare_except", "medium", [["bare except"], ["except", "pass"], ["swallow", "error"], ["silent", "error"]]),
        Bug("command_injection", "critical", [["command", "inject"], ["os.system"], ["shell", "inject"], ["rm -rf"]]),
    ],
)

_WEB = BugTask(
    id="web",
    prompt="Find ALL security bugs in this web handler.",
    code='''import random

def make_token():
    return str(random.randint(1000, 9999))

def render_profile(name):
    return "<div>Hello " + name + "</div>"

def delete_account(request, user_id):
    db_delete(user_id)
    return "deleted"

def redirect(request):
    return Redirect(request.params["next"])
''',
    planted=[
        Bug("weak_random_token", "high", [["weak", "random"], ["predictable", "token"], ["random.randint", "token"], ["insecure", "random"], ["not", "cryptograph"]]),
        Bug("xss", "high", [["xss"], ["cross-site script"], ["unescap"], ["html", "inject"]]),
        Bug("missing_authz", "critical", [["authoriz"], ["access control"], ["missing", "auth"], ["no", "permission"], ["idor"]]),
        Bug("open_redirect", "medium", [["open redirect"], ["unvalidated", "redirect"], ["redirect", "user"]]),
    ],
)

_CONCURRENCY = BugTask(
    id="concurrency",
    prompt="Find ALL concurrency and correctness bugs in this code.",
    code='''balance = 0

def deposit(amount):
    global balance
    balance = balance + amount

def transfer(accounts, src, dst, amt):
    if accounts[src] >= amt:
        accounts[dst] += amt
        accounts[src] -= amt

cache = {}
def get(key, compute):
    if key not in cache:
        cache[key] = compute(key)
    return cache[key]
''',
    planted=[
        Bug("race_deposit", "high", [["race", "condition"], ["not", "atomic"], ["no", "lock"], ["data race"], ["concurren", "balance"]]),
        Bug("check_then_act", "high", [["check-then-act"], ["check then act"], ["toctou"], ["time-of-check"], ["race", "transfer"]]),
        Bug("cache_race", "medium", [["cache", "race"], ["cache", "concurren"], ["thread", "cache"], ["non-atomic", "cache"]]),
    ],
)

# Near-clean: one genuine subtle bug; the rest is fine. Measures false-positive control.
_NEARCLEAN = BugTask(
    id="nearclean",
    prompt="Find ALL real bugs in this code. Do not report stylistic nits.",
    code='''def average(nums):
    return sum(nums) / len(nums)

def first_or_default(items, default=None):
    return items[0] if items else default

def retry(fn, attempts=3):
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
    raise last
''',
    near_clean=True,
    planted=[
        Bug("div_by_zero", "medium", [["divide by zero"], ["division by zero"], ["empty", "list"], ["len(nums)", "zero"], ["zerodivision"]]),
    ],
)

# HARD tier: a larger service with MANY bugs of varied subtlety — designed so a
# single confident pass tends to catch the obvious ones and MISS the subtle ones
# (recall breadth is where decompose+loop+multi-finder should pull ahead). Also
# seeds a couple of nit-traps (== None, unused var) that are NOT real bugs, to
# keep precision honest.
_BIGBUG = BugTask(
    id="bigbug",
    prompt="Find ALL real bugs (security, correctness, concurrency, resource) in this service. Ignore pure style nits.",
    code='''import os, hashlib, sqlite3, random, threading

SESSION_SECRET = "s3cr3t-key-do-not-share"

_counter = 0
def next_id():
    global _counter
    _counter = _counter + 1          # race: non-atomic read-modify-write
    return _counter

def hash_password(pw):
    return hashlib.md5(pw.encode()).hexdigest()   # weak hash for passwords

def login(db, user, pw):
    row = db.execute("SELECT pw FROM users WHERE name='%s'" % user).fetchone()  # sql injection
    return row and row[0] == hash_password(pw)

def read_report(base, name):
    full = os.path.join(base, name)               # path traversal: name may be ../../etc
    fh = open(full)
    return fh.read()                              # file handle leaked (never closed)

def page(items, page_num, size=10):
    start = page_num * size
    return items[start:start + size + 1]          # off-by-one: returns size+1 rows

def get_order(db, requester, order_id):
    return db.execute("SELECT * FROM orders WHERE id=%d" % order_id).fetchone()  # IDOR: no owner check

def add_tag(tag, tags=[]):                         # mutable default argument
    tags.append(tag)
    return tags

def token():
    return hashlib.md5(str(random.random()).encode()).hexdigest()  # predictable token (weak RNG)

def parse(data):
    try:
        return int(data)
    except:
        return None                                # bare except swallows everything

def avg(xs):
    return sum(xs) // len(xs)                       # integer division + ZeroDivision on empty

def run_hook(cmd):
    os.system("/bin/sh -c " + cmd)                 # command injection
''',
    planted=[
        Bug("race_counter", "high", [["race"], ["not atomic"], ["non-atomic"], ["thread", "counter"], ["lock", "counter"]]),
        Bug("weak_password_hash", "high", [["md5", "password"], ["weak", "hash"], ["insecure", "hash"], ["md5", "weak"]]),
        Bug("sql_injection", "critical", [["sql", "inject"], ["%s", "query"], ["string", "format", "sql"]]),
        Bug("path_traversal", "high", [["path", "travers"], ["../"], ["directory", "travers"]]),
        Bug("file_leak", "medium", [["not", "close"], ["file", "leak"], ["unclosed"], ["handle", "leak"]]),
        Bug("pagination_off_by_one", "medium", [["off-by-one"], ["off by one"], ["size + 1"], ["size+1"], ["extra row"], ["one too many"]]),
        Bug("idor", "critical", [["idor"], ["owner", "check"], ["access control"], ["authoriz"], ["any order"]]),
        Bug("mutable_default", "medium", [["mutable default"], ["default", "argument"], ["shared", "list", "default"]]),
        Bug("weak_token_rng", "high", [["predictable", "token"], ["weak", "random"], ["random.random", "token"], ["insecure", "random"]]),
        Bug("bare_except", "low", [["bare except"], ["except", "swallow"], ["broad except"], ["catch", "everything"]]),
        Bug("avg_zero_div", "medium", [["division by zero"], ["zerodivision"], ["empty", "list"], ["len(xs)", "zero"]]),
        Bug("command_injection", "critical", [["command", "inject"], ["os.system"], ["shell", "inject"]]),
    ],
)

TASKS: List[BugTask] = [_AUTH, _FILEOPS, _WEB, _CONCURRENCY, _NEARCLEAN]
HARD_TASKS: List[BugTask] = [_BIGBUG]
ALL_TASKS: List[BugTask] = TASKS + HARD_TASKS


def total_planted() -> int:
    return sum(len(t.planted) for t in TASKS)
