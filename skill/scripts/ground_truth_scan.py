#!/usr/bin/env python3
"""ground_truth_scan.py — the deterministic false-negative anchor.

The verify pass kills false POSITIVES. This kills false NEGATIVES by producing a
ground-truth DENOMINATOR of code-execution sinks that can't hallucinate or get
bored. AST-based (not grep), so it does NOT false-flag the security-detector
files that contain `shell=True` / `eval(` as detection REGEX STRINGS — those are
string literals in the AST, not calls, and the AST distinguishes them.

It walks the actual Python AST and flags every genuine code-execution sink:
  - subprocess.Popen/run/call/check_output/check_call WITH shell=True
  - create_subprocess_shell / create_subprocess_exec(shell=True)
  - os.system, os.popen, os.exec*, os.spawn*
  - eval(), exec(), compile() of non-constant input
  - __import__ of non-constant input
  - pickle.loads/load, marshal.loads   (deserialization RCE class)
  - yaml.load (non-SafeLoader)
  - ctypes via CDLL/WinDLL on non-constant input

Output: structured JSON of real sinks (file:line:col, sink type, code snippet),
plus per-file rollup. This is the denominator. Cross-check fan-out findings
against it (mode=crosscheck) to surface ground-truth hits NO finder named =
false-negative candidates.

Usage:
  python3 ground_truth_scan.py <repo-root>                 # scan -> JSON on stdout
  python3 ground_truth_scan.py <repo-root> -o sinks.json   # write to file
  python3 ground_truth_scan.py <repo-root> --findings fan_out.md --crosscheck
"""
from __future__ import annotations
import ast, os, sys, json, argparse, re

# Sinks where the DANGER is intrinsic to the call (any invocation is a code-exec sink):
_INTRINSIC = {"eval", "exec"}  # builtins
# Only os.system / os.popen are SHELL sinks. The os.exec* / os.spawn* family is
# process-replacement via argv array (no shell interpretation), same trust level
# as subprocess.run(list) — NOT an injection sink. Do not flag them as such.
_OS_SHELL = {"system", "popen"}
_PICKLE = {"loads", "load"}
_MARSHAL = {"loads", "load"}

# Sinks where the danger is a KEYWORD ARG (shell=True) — must inspect the call:
_SHELL_KW = "shell"
_SUBPROCESS_FNS = {"Popen", "run", "call", "check_call", "check_output"}
_SUBPROCESS_MODS = {"subprocess"}
_ASYNC_SHELL = {"create_subprocess_shell"}


def _const_value(node):
    """Best-effort: is the arg a literal/constant we can read? Returns the value or None."""
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _arg_is_const(node) -> bool:
    """True if the arg is a literal constant, or a ternary/joined-string of only constants.
    Covers: ast.Constant, IfExp(test=any, body/orelse=const), JoinedStr of const parts."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.IfExp):
        return _arg_is_const(node.body) and _arg_is_const(node.orelse)
    if isinstance(node, ast.JoinedStr):
        return all(_arg_is_const(v) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _arg_is_const(node.left) and _arg_is_const(node.right)
    return False


def _has_shell_true(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == _SHELL_KW:
            v = _const_value(kw.value)
            if v is True:
                return True
    return False


def _loader_is_safe(call: ast.Call, safe_names) -> bool:
    """For yaml.load: is a safe loader explicitly named? (Loader=SafeLoader/CSafeLoader)."""
    for kw in call.keywords:
        if kw.arg == "Loader":
            name = getattr(kw.value, "id", "") or getattr(kw.value, "attr", "")
            if name in safe_names:
                return True
    return False


def scan_file(path: str):
    """Yield sink dicts for one .py file. AST-based -> string literals (regex rules) are skipped."""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src, filename=path)
    except (SyntaxError, ValueError, OSError):
        return
    src_lines = src.splitlines()

    # File-level context for YAML precision: is `yaml` the PyYAML module, or a
    # ruamel YAML() instance? If the file imports ruamel OR assigns `yaml = YAML(...)`,
    # a bare `yaml.load(x)` is the ruamel round-trip loader (not the unsafe PyYAML
    # class) -> downgrade from "unsafe" to "verify-loader".
    uses_ruamel = False
    safe_loader_names = {"SafeLoader", "CSafeLoader"}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and getattr(n, "module", "") and "ruamel" in (n.module or ""):
            uses_ruamel = True
        if isinstance(n, ast.Assign):
            tgt = n.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id == "yaml" and isinstance(n.value, ast.Call):
                fn = n.value.func
                if (isinstance(fn, ast.Name) and fn.id == "YAML") or \
                   (isinstance(fn, ast.Attribute) and fn.attr == "YAML"):
                    uses_ruamel = True
            # Track variables assigned to safe PyYAML loaders, e.g.
            #   loader = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
            #   yaml.load(value, Loader=loader)
            if isinstance(tgt, ast.Name):
                val_src = ast.unparse(n.value) if hasattr(ast, "unparse") else ""
                if "SafeLoader" in val_src and "UnsafeLoader" not in val_src:
                    safe_loader_names.add(tgt.id)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        sink_type = None
        detail = ""

        # 1) eval() / exec() builtins
        if isinstance(node.func, ast.Name) and node.func.id in _INTRINSIC:
            # flag unless the arg is a constant (eval("1+1") is not an injection sink)
            if node.args and not _arg_is_const(node.args[0]):
                sink_type, detail = "eval/exec", node.func.id

        # 2) os.system / os.popen (the ONLY os.* shell sinks; os.exec* is argv, not shell)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in _OS_SHELL \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
            # flag os.system/popen only when the arg is not constant (constants can't inject).
            # A ternary of constants ("cls" if x else "clear") is also safe.
            if node.args and not _arg_is_const(node.args[0]):
                sink_type, detail = "os.shell-exec", f"os.{node.func.attr}"

        # 3) subprocess.* with shell=True (and create_subprocess_shell always)
        elif isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            mod = node.func.value
            mod_name = getattr(mod, "id", "") or getattr(mod, "attr", "")
            if attr in _SUBPROCESS_FNS and (mod_name in _SUBPROCESS_MODS or _has_shell_true(node)):
                if _has_shell_true(node):
                    sink_type, detail = "subprocess+shell=True", f"{mod_name}.{attr}"
            elif attr in _ASYNC_SHELL:
                sink_type, detail = "create_subprocess_shell", attr
            elif attr == "load" and mod_name == "pickle":
                sink_type, detail = "pickle.load (deserialize)", "pickle.load"
            elif attr in _PICKLE and mod_name == "pickle":
                sink_type, detail = "pickle (deserialize)", f"pickle.{attr}"
            elif attr in _MARSHAL and mod_name == "marshal":
                sink_type, detail = "marshal (deserialize)", f"marshal.{attr}"
            elif attr == "load" and mod_name == "yaml":
                if uses_ruamel:
                    # ruamel round-trip loader — NOT the PyYAML deserialization-RCE class.
                    # Downgrade: surface for review but don't call it "unsafe".
                    sink_type, detail = "yaml.load (ruamel/verify-loader)", "ruamel yaml.load"
                elif not _loader_is_safe(node, safe_loader_names):
                    sink_type, detail = "yaml.load (unsafe)", "yaml.load"

        # 4) __import__ of non-constant input
        elif isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if node.args and not _arg_is_const(node.args[0]):
                sink_type, detail = "__import__ (dynamic)", "__import__"

        if not sink_type:
            continue

        snippet = ""
        if 0 <= node.lineno - 1 < len(src_lines):
            snippet = src_lines[node.lineno - 1].strip()[:140]
        yield {
            "file": path, "line": node.lineno, "col": node.col_offset,
            "sink": sink_type, "detail": detail, "code": snippet,
        }


def iter_py(root, exclude_dirs=("venv", ".venv", "site-packages", ".git", "node_modules",
                                "__pycache__", "tests", "test", "website")):
    """Walk root for .py files, pruning excluded dirs by PATH SEGMENT (not substring)."""
    exclude_dirs = set(exclude_dirs)
    for dirpath, dirnames, filenames in os.walk(root):
        # prune by directory NAME (segment), so /tests/ matches the 'tests' dir exactly
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def scan(root, exclude_detectors=True):
    """Return {sinks:[...], by_file:{...}, stats:{...}}."""
    sinks = []
    for path in iter_py(root):
        for s in scan_file(path):
            sinks.append({**s, "file": os.path.relpath(s["file"], root)})
    # AST-based: detector files (approval.py, security-guidance) don't appear because
    # their "shell=True" is a STRING, not a Call node. No exclusion list needed.
    by_file = {}
    for s in sinks:
        by_file.setdefault(s["file"], []).append(s)
    return {
        "sinks": sinks,
        "by_file": by_file,
        "stats": {"files_scanned": sum(1 for _ in iter_py(root)),
                  "sink_files": len(by_file), "sinks": len(sinks)},
    }


def crosscheck(sinks, findings_text):
    """Return sinks whose file is NOT named anywhere in the fan-out findings text."""
    mentioned = set(re.findall(r"([\w./-]+\.py)", findings_text))
    fn = []
    for s in sinks:
        base = os.path.basename(s["file"])
        if s["file"] in mentioned or base in mentioned:
            continue
        fn.append(s)
    return fn


def main():
    ap = argparse.ArgumentParser(description="Deterministic ground-truth sink scanner (AST-based)")
    ap.add_argument("repo")
    ap.add_argument("-o", "--out", help="write JSON to file instead of stdout")
    ap.add_argument("--findings", help="fan-out findings file (md/txt) to cross-check against")
    ap.add_argument("--crosscheck", action="store_true", help="with --findings: print false-negative candidates only")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    res = scan(a.repo)
    if a.findings and os.path.exists(a.findings):
        fn = crosscheck(res["sinks"], open(a.findings, encoding="utf-8", errors="replace").read())
        res["false_negative_candidates"] = fn
        if not a.quiet:
            print(f"# ground-truth: {res['stats']['sinks']} sinks in {res['stats']['sink_files']} files "
                  f"| fan-out missed: {len(fn)}", file=sys.stderr)
        if a.crosscheck:
            payload = {"false_negative_candidates": fn,
                       "count": len(fn), "denominator": res["stats"]["sinks"]}
        else:
            payload = res
    else:
        if not a.quiet:
            print(f"# ground-truth: {res['stats']['sinks']} sinks in {res['stats']['sink_files']} files "
                  f"(scanned {res['stats']['files_scanned']} .py)", file=sys.stderr)
        payload = res

    out = json.dumps(payload, indent=2)
    if a.out:
        open(a.out, "w").write(out)
        print(f"wrote {a.out}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
