"""triage.py — discernment. The single most important lesson from the benchmark.

Ultracode lost on easy tasks because it ALWAYS went full-metal. A real ultracode
operator doesn't: it does a quick solo pass, then asks "would spinning up a
multi-agent orchestration actually change the answer, or am I already done?" —
and most of the time, stays solo. That judgment is the difference between a 78×-
cost gimmick and a tool you leave on.

This module is that judgment as a cheap, tools-off call: given a solo attempt,
decide whether to escalate. Orchestrate ONLY when the task is large, multi-
faceted, high-stakes, or solo confidence is low. Default to solo — exactly the
doctrine's restraint rule, now applied to the harness's own effort.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ultracode.adapters import aux_call, extract_json, runtime_from_agent


@dataclass
class TriageVerdict:
    orchestrate: bool
    confidence: float          # solo self-confidence 0..1
    stakes: str                # low | medium | high
    gaps: List[str] = field(default_factory=list)
    reason: str = ""


_TRIAGE_SYSTEM = (
    "You are deciding whether to escalate a task from a single solo pass to an expensive multi-agent "
    "orchestration (decompose -> parallel finders -> adversarial verification -> synthesis). Orchestration "
    "costs 30-80x the tokens and adds latency and noise, so it must EARN its cost. Recommend it ONLY when "
    "at least one is clearly true: the task is large or spans many files/modules; it is multi-faceted with "
    "several independent concerns; it is high-stakes/irreversible; or your solo confidence is low / you can "
    "name concrete things you likely missed. If the solo pass is already complete and high-confidence on a "
    "bounded task, STAY SOLO. Bias toward solo — that is the disciplined default."
)


def assess(
    task: str,
    solo_summary: str,
    *,
    context_size: int = 0,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    agent: Any = None,
    model: Optional[str] = None,
) -> TriageVerdict:
    """Decide whether orchestration would materially improve on the solo attempt."""
    user = (
        f"TASK:\n{task}\n\n"
        f"INPUT SIZE: ~{context_size} chars.\n\n"
        f"SOLO ATTEMPT (what one pass already produced):\n{solo_summary[:4000]}\n\n"
        "Would a full multi-agent orchestration MATERIALLY improve this, or is the solo attempt already "
        "complete and high-confidence?\n"
        'Reply with ONLY JSON: {"confidence": 0.0-1.0, "stakes": "low|medium|high", '
        '"gaps": ["<concrete thing the solo pass likely missed>", ...], "orchestrate": true|false, '
        '"reason": "<one line>"}'
    )
    try:
        text = aux_call(
            [{"role": "system", "content": _TRIAGE_SYSTEM}, {"role": "user", "content": user}],
            model=model, temperature=0.2, max_tokens=1000,
            main_runtime=runtime_from_agent(agent), call_fn=aux_call_fn,
        )
    except Exception:
        # if triage is unavailable, default to NOT orchestrating (cheap, safe, restraint)
        return TriageVerdict(orchestrate=False, confidence=0.5, stakes="low", reason="triage unavailable; staying solo")

    parsed = extract_json(text)
    if not isinstance(parsed, dict):
        return TriageVerdict(orchestrate=False, confidence=0.5, stakes="low", reason="triage unparseable; staying solo")

    conf = float(parsed.get("confidence", 0.5) or 0.5)
    stakes = str(parsed.get("stakes", "low")).strip().lower()
    gaps = [str(g).strip() for g in parsed.get("gaps", []) if str(g).strip()]
    orchestrate = bool(parsed.get("orchestrate", False))
    # Guardrail: even if the model says solo, escalate when it admits low confidence
    # on high stakes — and never orchestrate a confidently-complete low-stakes task.
    if stakes == "high" and conf < 0.8:
        orchestrate = True
    if stakes == "low" and conf >= 0.85 and not gaps:
        orchestrate = False
    return TriageVerdict(
        orchestrate=orchestrate, confidence=conf, stakes=stakes, gaps=gaps,
        reason=str(parsed.get("reason", "")).strip(),
    )
