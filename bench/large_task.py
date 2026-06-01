"""A LARGE multi-module codebase with bugs scattered across the whole span.

The small tasks proved a ceiling: any competent model one-shots a 40-line snippet.
The hypothesis ultracode needs to earn its cost: on a big input, single-shot
ATTENTION dilutes (lost-in-the-middle) and some bugs get missed, while decomposed
finders each focus on one module and find more. If single-shot recall drops below
ultracode's here, that is the regime where the harness pays for itself. If not,
that is an honest negative result and we report it.

~18 planted bugs across ~5 modules, deliberately spread head-to-tail.
"""

from bench.tasks import Bug, BugTask

_CODE = '''# ===================== module: config.py =====================
import os, hashlib, random, sqlite3, threading, time, pickle, base64

DB_PATH = "app.db"
JWT_SECRET = "change-me-in-prod"                       # BUG: hardcoded secret
DEBUG = True
ALLOWED_HOSTS = ["*"]                                  # BUG: wildcard allowed hosts

def load_config(path):
    with open(path) as f:
        data = f.read()
    return eval(data)                                  # BUG: eval of config file (RCE)

def feature_enabled(name, flags={}):                   # BUG: mutable default argument
    flags[name] = True
    return flags.get(name, False)

# ===================== module: db.py =========================
_conn = None
def get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _conn                                        # BUG: shared connection across threads, no lock

def find_user(name):
    cur = get_conn().cursor()
    cur.execute("SELECT * FROM users WHERE name = '%s'" % name)   # BUG: SQL injection
    return cur.fetchone()

def list_orders(user_id, limit):
    cur = get_conn().cursor()
    cur.execute("SELECT * FROM orders WHERE user_id = %s LIMIT %s" % (user_id, limit))  # BUG: SQL injection (2)
    return cur.fetchall()

def save_blob(key, obj):
    data = base64.b64encode(pickle.dumps(obj))
    get_conn().execute("INSERT INTO blobs VALUES (?, ?)", (key, data))

def load_blob(key):
    row = get_conn().execute("SELECT data FROM blobs WHERE k=?", (key,)).fetchone()
    return pickle.loads(base64.b64decode(row[0]))       # BUG: insecure deserialization (pickle)

# ===================== module: auth.py =======================
def hash_pw(pw):
    return hashlib.sha1(pw.encode()).hexdigest()        # BUG: weak/unsalted hash (sha1)

def make_token(user_id):
    return str(user_id) + "-" + str(random.random())    # BUG: predictable token (weak RNG + guessable)

def check_admin(user):
    if user.get("role") == "admin" or user.get("is_admin"):
        return True
    return False

def login(name, pw):
    u = find_user(name)
    if not u:
        return None
    if u[2] == hash_pw(pw):
        return make_token(u[0])
    return None

def reset_password(user, new_pw, requester):
    # BUG: missing authorization — requester never checked against user
    get_conn().execute("UPDATE users SET pw=? WHERE id=?", (hash_pw(new_pw), user["id"]))
    return True

# ===================== module: api.py ========================
def render(name):
    return "<h1>Welcome " + name + "</h1>"              # BUG: XSS (unescaped output)

def redirect_to(req):
    return {"Location": req["params"]["next"]}          # BUG: open redirect (unvalidated)

def handle_upload(base, filename, content):
    path = base + "/" + filename                        # BUG: path traversal in filename
    with open(path, "w") as f:
        f.write(content)
    return path

def paginate(rows, page, per=20):
    start = (page - 1) * per
    return rows[start:start + per + 1]                  # BUG: off-by-one (returns per+1)

def get_balance(accounts, uid):
    return accounts[uid]                                # BUG: KeyError on missing uid (no guard)

def transfer(accounts, src, dst, amt):
    if accounts[src] >= amt:                            # BUG: check-then-act race + no lock
        accounts[dst] += amt
        accounts[src] -= amt

# ===================== module: utils.py ======================
_cache = {}
def memoize(key, fn):
    if key not in _cache:
        _cache[key] = fn()                              # BUG: cache race (non-atomic check-then-set)
    return _cache[key]

def percent(part, whole):
    return part / whole * 100                           # BUG: ZeroDivisionError when whole == 0

def retry(fn, attempts=3):
    for _ in range(attempts):
        try:
            return fn()
        except:                                         # BUG: bare except swallows all
            time.sleep(0.1)
    return None

def parse_amount(s):
    return float(s)                                     # (ok-ish)

def run_job(cmd):
    os.system(cmd)                                       # BUG: command injection
'''

def _filler(start, count):
    """Generate `count` plausible, CORRECT helper functions — the haystack the
    bugs hide in. All are genuinely bug-free so they should NOT be flagged."""
    templates = [
        "def util_{n}(items):\n    return [x for x in items if x is not None]",
        "def util_{n}(a, b):\n    return a if a > b else b",
        "def util_{n}(s):\n    return s.strip().lower()",
        "def util_{n}(d, key, default=None):\n    return d.get(key, default)",
        "def util_{n}(xs):\n    total = 0\n    for x in xs:\n        total += x\n    return total",
        "def util_{n}(text):\n    return len(text.split())",
        "def util_{n}(n):\n    return n * (n + 1) // 2",
        "def util_{n}(seq):\n    return list(reversed(seq))",
        "def util_{n}(a, b):\n    return {{'sum': a + b, 'diff': a - b}}",
        "def util_{n}(xs):\n    return sorted(set(xs))",
        "def util_{n}(s, n):\n    return s[:n] if len(s) > n else s",
        "def util_{n}(d):\n    return {{k: v for k, v in d.items() if v}}",
    ]
    return "\n\n".join(templates[(start + i) % len(templates)].format(n=start + i) for i in range(count))


def _make_large2():
    """Scatter the 21 buggy functions through ~60 correct filler functions, so
    bugs are SPARSE (~1 per 30 lines) in a ~700-line mostly-correct file — the
    needle-in-haystack regime that actually stresses single-shot recall."""
    parts = _CODE.split("# =====================")
    out = [parts[0], _filler(0, 45)]
    fi = 45
    for chunk in parts[1:]:
        out.append("# =====================" + chunk)
        out.append(_filler(fi, 40))
        fi += 40
    return "\n\n".join(out)


_CODE_LARGE2 = _make_large2()

BUG_TASK = BugTask(
    id="large",
    prompt="Audit this multi-module Python service and find ALL real security and correctness bugs. Ignore pure style nits.",
    code=_CODE,
    planted=[
        Bug("hardcoded_secret", "high", [["hardcod", "secret"], ["jwt_secret"], ["hardcod", "key"]]),
        Bug("wildcard_hosts", "medium", [["wildcard", "host"], ["allowed_hosts"], ['allowed', '"*"'], ["allow", "all host"]]),
        Bug("config_eval_rce", "critical", [["eval", "config"], ["eval"], ["rce", "config"], ["arbitrary code"]]),
        Bug("mutable_default", "medium", [["mutable default"], ["default", "argument"], ["flags={}"], ["shared", "default"]]),
        Bug("shared_conn_threads", "medium", [["shared", "connection"], ["check_same_thread"], ["thread", "connection"], ["connection", "race"]]),
        Bug("sql_injection_user", "critical", [["sql inject", "name"], ["find_user", "inject"], ["sql", "inject"]]),
        Bug("sql_injection_orders", "critical", [["list_orders", "inject"], ["sql inject", "order"], ["%s", "inject"], ["second", "sql"]]),
        Bug("insecure_pickle", "high", [["pickle", "insecur"], ["pickle.loads"], ["deserial"], ["unpickle"]]),
        Bug("weak_hash", "high", [["sha1", "hash"], ["weak", "hash"], ["unsalted"], ["sha-1"]]),
        Bug("predictable_token", "high", [["predictable", "token"], ["weak", "random"], ["random.random"], ["guessable", "token"]]),
        Bug("missing_authz_reset", "critical", [["missing", "authoriz"], ["reset_password", "auth"], ["requester", "check"], ["access control"]]),
        Bug("xss", "high", [["xss"], ["unescap"], ["cross-site"], ["html", "inject"]]),
        Bug("open_redirect", "medium", [["open redirect"], ["unvalidated", "redirect"], ["redirect", "next"]]),
        Bug("path_traversal", "high", [["path", "travers"], ["filename", "travers"], ["../"]]),
        Bug("pagination_off_by_one", "medium", [["off-by-one"], ["off by one"], ["per + 1"], ["per+1"], ["extra row"]]),
        Bug("balance_keyerror", "low", [["keyerror", "balance"], ["missing", "uid"], ["get_balance", "guard"], ["unguarded", "dict"]]),
        Bug("transfer_race", "high", [["transfer", "race"], ["check-then-act"], ["toctou"], ["race", "transfer"]]),
        Bug("cache_race", "medium", [["cache", "race"], ["non-atomic", "cache"], ["memoize", "race"]]),
        Bug("percent_zero_div", "medium", [["division by zero"], ["zerodivision"], ["whole", "zero"], ["percent", "zero"]]),
        Bug("bare_except", "low", [["bare except"], ["except", "swallow"], ["broad except"]]),
        Bug("command_injection", "critical", [["command inject"], ["os.system"], ["run_job", "inject"]]),
    ],
)

# Same 21 bugs, but SPARSE in a ~700-line mostly-correct file (needle-in-haystack).
BUG_TASK_LARGE2 = BugTask(
    id="large2",
    prompt="Audit this large multi-module Python service and find ALL real security and correctness bugs. The codebase is mostly correct; the bugs are sparse. Ignore pure style nits.",
    code=_CODE_LARGE2,
    planted=BUG_TASK.planted,
)
