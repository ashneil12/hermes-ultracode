"""mode.py — the /ultracode toggle: cache-safe standing injection + xhigh effort.

Enabling ultracode does two things to the live agent, both reversible:
  1. pins reasoning to xhigh (snapshot/restore, one source of truth);
  2. appends a compact standing directive to ``agent.ephemeral_system_prompt`` —
     which CONTRACTS.md §5 confirms is injected at API-call time, AFTER the cached
     system-prompt prefix, so it never breaks the Anthropic prompt cache. The
     directive is byte-stable across turns, so it stays cache-safe.

The directive is the *standing default*; the real enforcement lives in the
agent/ultracode harness (the structure the model can't bypass). This is the
"flip the behavior" surface — `/ultracode [on|off|status]`.
"""

from __future__ import annotations

from typing import Any

from ultracode.reasoning import build_reasoning_config

# Compact standing reminder. Operational, not aspirational — a weak model must be
# able to act on it. The full doctrine is in DOCTRINE.md / the ultracode SKILL.
ULTRACODE_DIRECTIVE = (
    "[ULTRACODE MODE] Maximum rigor; token cost is not a constraint, being confidently wrong is. "
    "For substantive tasks (debugging, audits, 'find all X', research, high-stakes builds): "
    "(1) SCOPE before fanning out — recon first, decompose by the problem-native axis "
    "(hypothesis/lens/region), never one subtask per file. "
    "(2) FAN OUT independent units with delegate_task. "
    "(3) ADVERSARIALLY VERIFY every load-bearing finding with independent skeptics, each a DIFFERENT "
    "lens, each defaulting to REFUTED under uncertainty; a verdict with no stated mechanism does not count; "
    "your finders' reports are testimony, not fact. "
    "(4) For 'find all', LOOP until two rounds find nothing new, then run a completeness critic. "
    "(5) GROUND-TRUTH every load-bearing conclusion once by actually running/reading/testing it — "
    "reasoning is never a substitute for checking. "
    "(6) SYNTHESIZE solo, lead with the load-bearing result, present only verified findings as fact, "
    "rank and compress, surface the strongest refuted objection as a minority report. "
    "(7) When the fan-out is LARGE and the split is scriptable (codebase-wide sweep, 100+ unit migration, "
    "multi-source research), reach for the `dynamic-workflow` skill — plan-in-code so the loop and "
    "intermediate exhaust live in a script and your context holds only the final verified answer; do the "
    "DETERMINISTIC part (list/parse/fetch) first, then fan out only the irreducibly-LLM step. "
    "COST DISCIPLINE: prove the recipe on a SCOPED slice, report its token cost, then offer full scale — "
    "never silently fan out hundreds of children. "
    "STAY SOLO on trivial/coupled/voice/conversational work — if you can't name what a second worker adds, use one. "
    "Never fan out over an unreproduced failure. Never silently cap. A green is evidence, not a conclusion."
)

_SAVED_RC = "_ultracode_saved_reasoning_config"
_SAVED_EPH = "_ultracode_saved_ephemeral"
_FLAG = "_ultracode_on"


def is_enabled(agent: Any) -> bool:
    return bool(getattr(agent, _FLAG, False))


def enable(agent: Any, *, effort: str = "xhigh") -> str:
    """Turn ultracode on for ``agent``. Idempotent. Returns a status line."""
    if agent is None:
        return "ultracode: no agent"
    if is_enabled(agent):
        return "ultracode: already on"
    # snapshot
    setattr(agent, _SAVED_RC, getattr(agent, "reasoning_config", None))
    setattr(agent, _SAVED_EPH, getattr(agent, "ephemeral_system_prompt", None))
    # apply: xhigh reasoning
    try:
        agent.reasoning_config = build_reasoning_config(effort)
    except Exception:
        pass
    # apply: standing directive, appended (cache-safe, API-call-time only)
    prior = getattr(agent, "ephemeral_system_prompt", None) or ""
    directive = ULTRACODE_DIRECTIVE
    try:
        agent.ephemeral_system_prompt = (prior + "\n\n" + directive).strip() if prior else directive
    except Exception:
        pass
    setattr(agent, _FLAG, True)
    return f"ultracode: ON (effort={effort}, standing directive injected)"


def disable(agent: Any) -> str:
    """Turn ultracode off and restore the prior reasoning/ephemeral state."""
    if agent is None:
        return "ultracode: no agent"
    if not is_enabled(agent):
        return "ultracode: already off"
    try:
        agent.reasoning_config = getattr(agent, _SAVED_RC, None)
    except Exception:
        pass
    try:
        agent.ephemeral_system_prompt = getattr(agent, _SAVED_EPH, None)
    except Exception:
        pass
    setattr(agent, _FLAG, False)
    return "ultracode: OFF (restored prior reasoning + ephemeral state)"


def status(agent: Any) -> str:
    if agent is None:
        return "ultracode: no agent"
    if not is_enabled(agent):
        return "ultracode: off"
    rc = getattr(agent, "reasoning_config", None) or {}
    return f"ultracode: ON (effort={rc.get('effort', '?')})"


def handle_command(agent: Any, arg: str = "") -> str:
    """Dispatch for a `/ultracode [on|off|status]` slash command."""
    a = (arg or "").strip().lower()
    if a in ("", "toggle"):
        return disable(agent) if is_enabled(agent) else enable(agent)
    if a in ("on", "enable", "start"):
        return enable(agent)
    if a in ("off", "disable", "stop"):
        return disable(agent)
    return status(agent)
