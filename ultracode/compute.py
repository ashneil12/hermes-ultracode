"""compute.py — execution as a reasoning aid.

A weak model's reasoning fails on systematic search / enumeration / simulation (find the
smallest binary multiple, min jug-pours, constrained knapsack, a long iteration) — but it
can WRITE correct code for exactly those, and the runtime executes it reliably. This is the
single biggest cognitive lever for a weak model: let it RUN the search instead of doing it
in its head, the same way an expert recognizes "this is computable" and writes the program.

The agent decides (it is told it MAY decline with NOT_COMPUTABLE for tasks that are pure
reasoning, like a logic puzzle). On a runtime error it gets ONE retry with the error fed
back. A successful run is ground truth for the computable part — high confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ultracode.adapters import aux_call, runtime_from_agent
from ultracode.execute import run_python


def _fenced_code(text: str) -> str:
    """Only a real ```python ...``` block counts as a program — unlike extract_code,
    bare prose does NOT fall back to being 'code' (so a NOT_COMPUTABLE / reasoning reply
    is never mistakenly executed)."""
    if not isinstance(text, str):
        return ""
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else ""


@dataclass
class ComputeResult:
    ran: bool = False          # a program was produced AND ran cleanly
    answer: str = ""           # the program's stdout (the computed answer)
    code: str = ""
    declined: bool = False     # the agent judged it NOT computable (pure reasoning)
    detail: str = ""


_SYS = (
    "You solve problems by WRITING AND RUNNING code when that is the reliable way. Given a problem, decide: "
    "is the ANSWER a concrete value (a number, a name, an enumerated assignment, a final state) that a program "
    "can compute WITHOUT error by brute-force / systematic search / enumeration / simulation / exact arithmetic? "
    "If YES, write a SINGLE self-contained Python 3 program (standard library only) that COMPUTES it — let the "
    "program do the work, do not reason it out. The program MUST print the COMPLETE answer to EVERY part the "
    "question asks for (if it asks for a configuration AND a count, print both; if it asks for the type of A, B "
    "and C, print all three) — print it clearly on the last line(s). Wrap the program in a ```python code block. "
    "Reply with exactly NOT_COMPUTABLE (and nothing else) if the task instead asks you to EXPLAIN, IDENTIFY, or "
    "JUSTIFY in prose — find-the-bug, which-step-of-the-proof-is-wrong, why-does-X — or is pure deductive "
    "reasoning where a value isn't really being computed; those need reasoning, not a program."
)


def computable_answer(
    task: str,
    *,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    agent: Any = None,
    model: Optional[str] = None,
    run_fn: Callable[..., Any] = run_python,
    timeout: float = 10.0,
    max_retries: int = 1,
) -> ComputeResult:
    """Let the agent write+run a program to compute the answer. Returns a ComputeResult;
    ran=True means the stdout is a trustworthy computed answer."""
    rt = runtime_from_agent(agent)
    messages = [{"role": "system", "content": _SYS}, {"role": "user", "content": task}]
    last_err, code = "", ""
    for attempt in range(max_retries + 1):
        try:
            reply = aux_call(messages, model=model, temperature=0.1, max_tokens=2500,
                             main_runtime=rt, call_fn=aux_call_fn)
        except Exception as exc:
            return ComputeResult(detail=f"aux unavailable: {exc}")
        code = _fenced_code(reply)
        if not code:
            # explicit decline, or pure-reasoning reply with no program -> fall through
            return ComputeResult(declined=True,
                                 detail="agent judged it pure reasoning" if "NOT_COMPUTABLE" in reply
                                 else "no program produced")
        res = run_fn(code, timeout=timeout)
        if res.ok:
            out = (res.stdout or "").strip()
            # keep the FULL program output (multi-part answers print several lines); the
            # last few lines are the answer. Cap to avoid runaway prints.
            ans = "\n".join(out.splitlines()[-8:]).strip() if out else ""
            return ComputeResult(ran=bool(ans), answer=ans, code=code, detail="computed by execution")
        # failed: feed the error back for one retry
        last_err = (res.stderr or "")[-600:] if not res.timed_out else "timed out"
        messages = messages + [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": f"That program failed with:\n{last_err}\nFix it and reprint the full corrected program."},
        ]
    return ComputeResult(code=code, detail=f"program failed after retries: {last_err}")
