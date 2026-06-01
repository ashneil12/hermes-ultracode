"""execute.py — run code for real, the only true exit from the closed loop.

The deepest finding in the doctrine: a solver verifying its own reasoning is an
epistemically CLOSED loop; more lenses just redistribute the same priors. The one
move that breaks it is non-inferential contact with reality — RUN it. Until now
the harness's verifiers only *reasoned*; this module lets them *execute* a repro
and let the interpreter, not the model, decide.

Safety: this runs model-generated code. It is therefore:
  * OPT-IN (config.execution_verify, default False),
  * isolated in a subprocess with a hard timeout,
  * run with a minimal environment (no inherited secrets) and output caps.
It is NOT a true sandbox (Python can't fully sandbox itself). Enable it only for
trusted/benchmark targets or behind a real sandbox (container/VM) in production.
The risk is real and named — never silently on.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecResult:
    ok: bool                 # process exited 0
    returncode: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool

    def as_dict(self):
        return {"ok": self.ok, "returncode": self.returncode, "stdout": self.stdout[-2000:],
                "stderr": self.stderr[-2000:], "timed_out": self.timed_out}


def run_python(code: str, *, timeout: float = 5.0, max_output: int = 8000) -> ExecResult:
    """Run a self-contained Python snippet in an isolated subprocess.

    Returns ExecResult. A repro that asserts the bug should exit 0 (ok=True) iff
    the bug reproduces — execution, not the model's say-so, is the verdict.
    """
    if not isinstance(code, str) or not code.strip():
        return ExecResult(False, None, "", "empty code", False)
    fd, path = tempfile.mkstemp(suffix=".py", prefix="ultracode_exec_")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(code)
        # minimal env: keep PATH (for the interpreter) but drop everything else
        # (no API keys, no secrets leak into model-generated code).
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            proc = subprocess.run(
                [sys.executable, "-I", path],  # -I: isolated mode (ignore env/user site)
                capture_output=True, text=True, timeout=timeout, env=env, cwd=tempfile.gettempdir(),
            )
            return ExecResult(
                ok=(proc.returncode == 0), returncode=proc.returncode,
                stdout=(proc.stdout or "")[:max_output], stderr=(proc.stderr or "")[:max_output],
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(False, None, "", f"timed out after {timeout}s", True)
        except Exception as exc:  # pragma: no cover - defensive
            return ExecResult(False, None, "", f"exec error: {exc}", False)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def extract_code(text: str) -> str:
    """Pull a python code block out of an LLM reply (fenced or bare)."""
    import re

    if not isinstance(text, str):
        return ""
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()
