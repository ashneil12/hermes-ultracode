"""Effort floor — drive the agent to xhigh for the duration of an ultracode run.

`run_conversation()` takes no per-call reasoning_config (it reads
`agent.reasoning_config`), so the faithful way to raise effort for a turn is to
snapshot the agent's reasoning_config, set xhigh, and restore it afterward —
exactly the turn-scoped save/set/restore pattern upstream PR #35821 used, but
with one source of truth and a real `finally` so a mid-run error can't leave the
agent stuck at xhigh.

This module is provider-agnostic: it only constructs the `{"enabled","effort"}`
dict. The provider profiles (Anthropic/OpenRouter/Kimi/Gemini/...) translate it
at request-build time. (Note the Opus-4.8 substring gap flagged in CONTRACTS.md
§4 — that is an anthropic_adapter concern, not this module's.)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_FALLBACK_LEVELS = ("minimal", "low", "medium", "high", "xhigh")


def valid_levels() -> tuple:
    try:
        from hermes_constants import VALID_REASONING_EFFORTS  # type: ignore

        return tuple(VALID_REASONING_EFFORTS)
    except Exception:
        return _FALLBACK_LEVELS


def build_reasoning_config(effort: str = "xhigh") -> Dict[str, Any]:
    """Return a reasoning_config dict for the given effort level.

    Mirrors hermes_constants.parse_reasoning_effort semantics: "none" disables
    reasoning; an unknown level falls back to xhigh (we are ultracode — bias up,
    not down) and is reported via the returned dict's ``_coerced`` marker.
    """
    if effort is None:
        return {"enabled": True, "effort": "xhigh"}
    norm = str(effort).strip().lower()
    if norm == "none":
        return {"enabled": False}
    if norm in valid_levels():
        return {"enabled": True, "effort": norm}
    # ultracode bias: unknown -> xhigh, not medium (and say we coerced)
    return {"enabled": True, "effort": "xhigh", "_coerced_from": norm}


class effort_scope:
    """Context manager that pins ``agent.reasoning_config`` to an effort level and
    restores the prior value on exit (even on exception).

    Tolerates ``agent is None`` (no-op) so harness code paths that run without a
    live agent — and unit tests — don't need to special-case it.

        with effort_scope(agent, "xhigh"):
            result = agent.run_conversation(user_message=task)
        # agent.reasoning_config is back to whatever it was
    """

    def __init__(self, agent: Any, effort: str = "xhigh"):
        self.agent = agent
        self.effort = effort
        self._saved: Optional[Dict[str, Any]] = None
        self._had_attr = False

    def __enter__(self) -> "effort_scope":
        if self.agent is None:
            return self
        self._had_attr = hasattr(self.agent, "reasoning_config")
        self._saved = getattr(self.agent, "reasoning_config", None)
        try:
            self.agent.reasoning_config = build_reasoning_config(self.effort)
        except Exception:
            # if the agent rejects attribute assignment, leave it untouched
            pass
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self.agent is None:
            return False
        try:
            if self._had_attr:
                self.agent.reasoning_config = self._saved
            else:
                # restore to None to match the pre-scope state
                self.agent.reasoning_config = None
        except Exception:
            pass
        return False  # never suppress exceptions
