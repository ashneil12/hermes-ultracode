"""install.py — point ultracode at a Hermes-style agent and wire it in, one command.

    python -m ultracode.install --agent /path/to/hermes-agent          # vendor + wire + report
    python -m ultracode.install --agent /path/to/hermes-agent --check  # dry-run, report only

What it does (all idempotent, no network, stdlib-only so it runs before the package is installed):
  1. Validates the host exposes ultracode's two bridge points
       - tools/delegate_tool.py        (fan-out: delegate_task)
       - agent/auxiliary_client.py     (a bounded LLM call: call_llm)
  2. Vendors the self-contained ``ultracode/`` package into the host (skipped if already importable),
     so ``import ultracode`` works with zero pip steps and zero third-party deps.
  3. Reports the host's delegate_task thread-safety, and notes that ``integration.threadsafe_delegate``
     makes concurrent fan-out safe at runtime regardless (the portable "delegate patch").
  4. Drops a copy-paste quickstart and prints the 3-line integration snippet.

The wiring itself is one import in the host's turn loop::

    from ultracode.integration import ultracode_run
    result = ultracode_run(task, parent_agent=self, context=src)   # decompose→fan-out→verify→synthesize
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent          # the ultracode/ package source
_PKG_NAME = _PKG_DIR.name                            # "ultracode" (standalone) / "ultracode" after sync
_SKIP = {"__pycache__", "bench", "tests", ".pytest_cache", "results"}

_SNIPPET = """\
    from ultracode.integration import ultracode_run

    result = ultracode_run(task, parent_agent=self, context=src)
    print(result.answer)        # synthesized + adversarially verified
"""

_QUICKSTART = '''\
"""ultracode_quickstart.py — auto-written by `python -m ultracode.install`.

Run a hard task through ultracode using THIS agent's own delegate/LLM bridges.
Call from anywhere you hold a live agent (e.g. inside a tool, or your turn loop).
"""
from ultracode.integration import ultracode_run


def demo(parent_agent, task: str, src: str = "") -> str:
    # parent_agent: a live Hermes agent (has .auxiliary_client and can delegate_task)
    result = ultracode_run(
        task,
        parent_agent=parent_agent,
        context=src,
        concurrency=8,          # parallel fan-out width; serialized safely under the hood
        execution_assist=False, # set True ONLY where code execution is sandboxed/trusted
    )
    return result.answer
'''


def _ok(m):   print(f"  \033[32m✓\033[0m {m}")
def _warn(m): print(f"  \033[33m!\033[0m {m}")
def _info(m): print(f"  \033[36m·\033[0m {m}")


def _thread_safety(delegate_src: Path) -> str:
    try:
        txt = delegate_src.read_text(errors="ignore")
    except OSError:
        return "unknown"
    if "threading.Lock" in txt or "threading.RLock" in txt or "_lock" in txt:
        return "host-locked"
    return "needs-wrapper"


def install(agent_path: Path, *, check: bool, write_example: bool) -> int:
    agent_path = agent_path.expanduser().resolve()
    print(f"\n\033[1multracode → {agent_path}\033[0m\n")
    if not agent_path.is_dir():
        print(f"  \033[31m✗\033[0m not a directory: {agent_path}")
        return 2

    # 1. bridge points
    delegate = agent_path / "tools" / "delegate_tool.py"
    auxcli = agent_path / "agent" / "auxiliary_client.py"
    has_delegate, has_aux = delegate.is_file(), auxcli.is_file()
    (_ok if has_delegate else _warn)(
        f"fan-out bridge: tools/delegate_tool.py {'found' if has_delegate else 'MISSING (pass delegate_fn= yourself)'}")
    (_ok if has_aux else _warn)(
        f"LLM bridge: agent/auxiliary_client.py {'found' if has_aux else 'MISSING (pass aux_call_fn= yourself)'}")

    # 2. vendor the package (unless already importable from the host)
    dest = agent_path / _PKG_NAME
    if dest.resolve() == _PKG_DIR.resolve():
        _info(f"package already lives in the host tree ({dest}) — nothing to vendor")
    elif check:
        _info(f"[check] would vendor {_PKG_NAME}/ → {dest}")
    else:
        shutil.copytree(
            _PKG_DIR, dest, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*_SKIP))
        _ok(f"vendored {_PKG_NAME}/ → {dest}  (self-contained, no third-party deps)")

    # 3. thread-safety of delegate_task
    if has_delegate:
        st = _thread_safety(delegate)
        if st == "host-locked":
            _ok("delegate_task already guards its shared state; threadsafe_delegate adds a cheap belt-and-braces RLock")
        elif st == "needs-wrapper":
            _warn("delegate_task shows no lock — ultracode.integration.threadsafe_delegate serializes it at "
                  "runtime so concurrent fan-out is safe (no source edit, idempotent)")
        else:
            _info("could not read delegate_task; threadsafe_delegate protects fan-out regardless")

    # 4. quickstart + snippet
    if write_example and not check:
        qs = agent_path / "ultracode_quickstart.py"
        qs.write_text(_QUICKSTART)
        _ok(f"wrote {qs.name}")

    print("\n\033[1mWire it in (one import in your turn loop / a tool):\033[0m\n")
    print(_SNIPPET)
    print("\033[1mVerify:\033[0m  python -c \"import ultracode.harness as h; print('ultracode ready')\"")
    print("\033[1mTest:\033[0m    python -m pytest tests/ -q -o addopts=\"\"   (no network)\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ultracode.install", description="Wire ultracode into a Hermes-style agent.")
    ap.add_argument("--agent", required=True, type=Path, help="path to the host agent repo")
    ap.add_argument("--check", action="store_true", help="dry-run: report only, vendor nothing")
    ap.add_argument("--no-example", action="store_true", help="do not write ultracode_quickstart.py")
    a = ap.parse_args(argv)
    return install(a.agent, check=a.check, write_example=not a.no_example)


if __name__ == "__main__":
    sys.exit(main())
