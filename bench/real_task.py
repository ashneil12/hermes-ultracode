"""Real-code benchmark task: we45/Vulnerable-Flask-App (cloned to /tmp).

A genuine 339-line Flask app with ~10 distinct, real, diverse vulnerabilities
spread head-to-tail — the closest thing to a real audit. Ground truth below is
the documented/obvious vuln set; signatures match likely model phrasings.
"""

import os
from bench.tasks import Bug, BugTask

_PATHS = [
    "/tmp/realrepo/Vulnerable-Flask-App/app/app.py",
    os.path.expanduser("~/realrepo/Vulnerable-Flask-App/app/app.py"),
]


def _load():
    for p in _PATHS:
        if os.path.exists(p):
            return open(p).read()
    return ""


_CODE = _load()

REAL_TASK = BugTask(
    id="vulnflask",
    prompt="Security-audit this real Flask application. Find ALL real security vulnerabilities (auth, injection, crypto, deserialization, access control). Ignore pure style.",
    code=_CODE,
    planted=[
        Bug("hardcoded_secret", "high", [["hardcod", "secret"], ["hardcoded", "key"], ["secret_key", "hardcod"], ["weak", "secret_key"], ["'secret'"]]),
        Bug("insecure_jwt_verify", "critical", [["verify=false"], ["verify", "false"], ["jwt", "not", "verif"], ["signature", "not", "verif"], ["insecure", "jwt"], ["alg", "none"], ["jwt", "bypass"]]),
        Bug("sql_injection", "critical", [["sql", "inject"], ["str_query"], ["string", "format", "query"], ["db.engine.execute"], ["%s", "query"]]),
        Bug("ssti", "critical", [["ssti"], ["template", "inject"], ["render_template_string"], ["server-side template"]]),
        Bug("md5_password", "high", [["md5", "password"], ["weak", "hash"], ["md5", "weak"], ["unsalted", "md5"]]),
        Bug("plaintext_password", "high", [["plaintext", "password"], ["password", "plain"], ["admin123"], ["plaintext", "credential"], ["password", "compared", "plain"]]),
        Bug("yaml_rce", "critical", [["yaml.load"], ["yaml", "unsafe"], ["yaml", "deserial"], ["yaml", "rce"], ["unsafe", "load"], ["yaml", "arbitrary"]]),
        Bug("idor", "high", [["idor"], ["access control"], ["authoriz", "customer"], ["any customer"], ["ownership", "check"], ["insecure direct object"]]),
        Bug("xxe", "high", [["xxe"], ["xml external"], ["external entity"]]),
        Bug("verbose_error_leak", "low", [["error", "leak"], ["stack", "trace", "expos"], ["verbose", "error"], ["exception", "expos"]]),
    ],
)

AVAILABLE = bool(_CODE)
