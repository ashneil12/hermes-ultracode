#!/usr/bin/env python3
"""bridge.py — run the user's ultracode harness on ANY backend via injection.

The harness (~/Projects/hermes-ultracode) was built to be backend-agnostic:
every call into a runtime goes through adapters.py, and delegate_fanout /
aux_call each accept an injectable function. This module supplies those
functions so the FULL engine (steering -> planner -> fanout -> verify_to_
convergence -> completeness critic -> synthesize) runs end-to-end WITHOUT the
Hermes runtime — on whatever delegate/LLM backend we hand it.

Two seams to fill in for live use (marked TODO_WIRE):
  * _delegate_fn  -> map onto the host's real parallel-subagent tool (TaskDelegate)
  * _call_fn      -> map onto the host's own bounded LLM call (planner/verify/critic)

Until wired, both default to deterministic fakes so the control flow is
testable with zero token spend (this is how the harness's own unit tests run).

Contracts (from adapters.py / CONTRACTS.md, verified against the repo):
  delegate_fn(tasks=[{...}], parent_agent, role) -> JSON str
    {"results": [{"task_index": i, "status": "completed", "summary": "..."}], ...}
  call_fn(messages=[...], model, temperature, max_tokens, tools, main_runtime)
    -> object whose .choices[0].message.content is the text.
"""
from __future__ import annotations
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

def _find_harness():
    here = os.path.dirname(os.path.abspath(__file__))
    for c in (os.environ.get("ULTRACODE_HARNESS", ""),
              os.path.normpath(os.path.join(here, "..", "..", "engine")),
              os.path.normpath(os.path.join(here, "..", "engine")),
              os.path.expanduser("~/Projects/hermes-ultracode")):
        if c and os.path.isdir(os.path.join(c, "ultracode")):
            return c
    return None

HARNESS = _find_harness()
if HARNESS and HARNESS not in sys.path:
    sys.path.insert(0, HARNESS)


# --------------------------------------------------------------------------
# SEAM 1 — parallel subagent fan-out. Wire to the host's real delegate tool.
# --------------------------------------------------------------------------
def _delegate_fn(*, tasks: List[Dict[str, Any]], parent_agent: Any = None,
                 role: str = "leaf") -> str:
    """Map the harness's delegate contract onto the host's parallel subagent tool.

    ARCHITECTURAL NOTE (learned by building it): this seam CANNOT be wired when
    harness.run() executes as a child Python PROCESS — a subprocess can't reach
    back up into the agent's TaskDelegate tool (that tool is invoked from the
    agent's own turn, not callable from spawned Python). So there are exactly two
    honest execution models:

      MODEL A (bench): run harness.run() in-process with a CONCURRENCY-SAFE LLM
        client as delegate_fn (e.g. bench/deepseek_client.DeepSeekClient.delegate_fn).
        This is how the benchmarks ran. Reproducible, self-contained, but the
        children are that client's calls, not the live agent.

      MODEL B (live, in-session): the AGENT is the conductor. It runs the harness's
        JUDGMENT modules as pure-Python helpers (steering.decide, schema.dedupe_
        findings, verify logic, the enumerate_corpus chunk/union/retry pattern) but
        does the FAN-OUT itself by calling TaskDelegate from its own turn, one
        leaf per chunk, then unions+dedups the returned file-lists. This is the
        ONLY model that uses the live agent's tools, and it's what the skill does
        in production. Validated live on clawsweeper (ghJson find-all, 120 files).

    This fake remains for offline control-flow testing (Model A unit path). Live
    work uses Model B, driven from the skill, not this function.
    """
    results = []
    for i, t in enumerate(tasks):
        goal = t.get("goal") or t.get("task") or t.get("prompt") or ""
        results.append({
            "task_index": i,
            "status": "completed",
            "summary": f"[FAKE delegate — use Model A (deepseek_client) or Model B (agent TaskDelegate)] {str(goal)[:100]}",
        })
    return json.dumps({"results": results, "total_duration_seconds": 0})


# --------------------------------------------------------------------------
# SEAM 2 — bounded, tools-off reasoning call (planner / synthesis / critic).
# --------------------------------------------------------------------------
class _Resp:
    """Minimal shape the harness reads: resp.choices[0].message.content."""
    def __init__(self, content: str):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


def _call_fn(*, messages: List[Dict[str, Any]], model=None, temperature=None,
             max_tokens=None, tools=None, main_runtime=None) -> Any:
    """Map the harness's aux call onto the host's own LLM.

    TODO_WIRE: replace with a real bounded completion. The harness uses this for
    planning, synthesis, and the completeness critic. Return any object exposing
    .choices[0].message.content.
    """
    last = messages[-1].get("content", "") if messages else ""
    return _Resp(f"[FAKE aux_call] would reason over: {str(last)[:160]}")


def make_config(**overrides):
    """Build an UltracodeConfig, applying any overrides (e.g. worker_model)."""
    from ultracode.config import UltracodeConfig  # type: ignore
    cfg = UltracodeConfig()
    for k, v in overrides.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def run_fanout(tasks, *, max_children=3, concurrency=None, retry_empty=1,
               worker_model=None, delegate_fn: Optional[Callable] = None):
    """Direct access to the deduped, retry-holes fan-out primitive."""
    from ultracode.adapters import delegate_fanout  # type: ignore
    return delegate_fanout(
        tasks, max_children=max_children, concurrency=concurrency,
        retry_empty=retry_empty, worker_model=worker_model,
        delegate_fn=delegate_fn or _delegate_fn,
    )


def smoke_test():
    """Prove the engine's control flow runs end-to-end on injected fakes."""
    from ultracode.steering import decide  # type: ignore
    print("== steering gate ==")
    d = decide("find all the auth-token leaks across the repo")
    print(f"  orchestrate={d.orchestrate} shape={d.shape.value} loop={d.loop_until_dry}")

    print("== injected fan-out (3 units, retry-empty on) ==")
    tasks = [{"goal": f"audit module {m}"} for m in ("auth", "billing", "session")]
    res = run_fanout(tasks, max_children=3, retry_empty=1)
    for r in res:
        print(f"  [{r['task_index']}] {r['status']}: {r['summary']}")

    print("== dedupe + agreement (schema) ==")
    from ultracode.schema import Finding, dedupe_findings  # type: ignore
    fs = [
        Finding(claim="POST /users/:id/role has no role check", locator="users.py:142"),
        Finding(claim="POST /users/:id/role has no role check", locator="users.py:142"),
        Finding(claim="JWT verified with verify=False", locator="auth.py:30"),
    ]
    deduped = dedupe_findings(fs)
    for f in deduped:
        ac = getattr(f, "agreement_count", 1)
        print(f"  {f.locator}: {f.claim[:50]} (agreement={ac})")
    print("\nOK: engine control flow runs on injected backend (no Hermes runtime).")


if __name__ == "__main__":
    smoke_test()
