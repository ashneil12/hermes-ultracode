"""integration.py — drop ultracode into a Hermes-style agent in one call.

A Hermes agent already exposes the two primitives ultracode needs:
  * ``tools.delegate_tool.delegate_task(tasks=[...], parent_agent, role) -> JSON str``  (fan-out)
  * ``agent.auxiliary_client.call_llm(messages=[...], ...) -> resp``                      (a bounded call)

This module wires those to the harness so the host can run::

    from ultracode.integration import ultracode_run
    result = ultracode_run("Audit this module for security bugs.", parent_agent=self, context=src)
    print(result.answer)

THREAD-SAFETY: concurrent fan-out hammers the host's ``delegate_task``. Some versions mutate
process-global state without a lock. ``threadsafe_delegate`` wraps the host call in a module
RLock so parallel waves are safe on ANY agent — the portable "delegate_task patch" applied at
runtime, no source edit, idempotent, survives version drift. (If the host is already locked,
the extra RLock is a cheap no-op.)
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from ultracode.config import UltracodeConfig
from ultracode.harness import run

_DELEGATE_LOCK = threading.RLock()


def threadsafe_delegate(delegate_fn: Optional[Callable[..., str]] = None) -> Callable[..., str]:
    """Return a delegate_fn whose host call is serialized by a process RLock, so concurrent
    ultracode fan-out can never race the host's delegate_task globals. Wraps a supplied fn,
    or lazily the host's ``tools.delegate_tool.delegate_task``."""
    def _host(*, tasks, parent_agent=None, role="leaf"):
        fn = delegate_fn
        if fn is None:
            from tools.delegate_tool import delegate_task as fn  # type: ignore  # lazy host import
        with _DELEGATE_LOCK:
            return fn(tasks=tasks, parent_agent=parent_agent, role=role)
    return _host


def ultracode_run(
    task: str,
    *,
    parent_agent: Any = None,
    context: str = "",
    concurrency: Optional[int] = 8,
    execution_assist: bool = False,
    delegate_fn: Optional[Callable[..., str]] = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    config: Optional[UltracodeConfig] = None,
    **run_kwargs: Any,
):
    """One-call ultracode entry wired to a Hermes agent.

    Uses the host's call_llm (via the harness default) and a thread-safe delegate fan-out.
    Pass ``execution_assist=True`` for the compute-as-evidence lever (runs model code — only
    where execution is sandboxed/trusted). Extra kwargs flow to ``harness.run``.
    """
    cfg = config or UltracodeConfig(concurrency=concurrency, execution_assist=execution_assist)
    return run(
        task,
        context=context,
        agent=parent_agent,
        delegate_fn=threadsafe_delegate(delegate_fn),
        aux_call_fn=aux_call_fn,   # None -> harness uses the host's auxiliary_client.call_llm
        config=cfg,
        **run_kwargs,
    )
