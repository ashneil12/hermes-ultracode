"""Completeness critic — the from-scratch "what's missing?" pass.

After discovery + verification, a single tools-off pass asks: what modality was
NOT run, what claim is unverified, what source is unread, what cell is unowned?
Its output becomes the next discovery round's targets (loop integration) and is
ALWAYS surfaced in the final report (no-silent-caps).

Honest caveat encoded in the contract (deep-residual lens): this critic is the
SAME model with correlated priors — "from-scratch" is a role, not true
independence. So its verdict is treated as UNKNOWN-not-clean: an empty gap list
means "I found no gap", never "there are no gaps". Genuine independence needs a
different generator (a tool, a fresh measurement, the human) — that escalation is
the harness's job, not this function's claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ultracode.adapters import aux_call, extract_json, runtime_from_agent
from ultracode.schema import Finding


@dataclass
class CritiqueResult:
    gaps: List[str] = field(default_factory=list)
    coverage_note: str = ""
    independent: bool = False  # always False for same-model critique; flagged honestly
    raw: str = ""


_CRITIC_SYSTEM = (
    "You are a completeness critic for an exhaustive investigation. You did NOT do the work; "
    "your only job is to find what is MISSING. Be specific and adversarial. "
    "You share the original solver's blind spots, so bias hard toward naming gaps over declaring done."
)


def completeness_critic(
    task: str,
    findings: List[Finding],
    *,
    caps_announced: Optional[List[str]] = None,
    agent: Any = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    model: Optional[str] = None,
) -> CritiqueResult:
    """Ask one tools-off pass what the investigation still misses.

    Returns gaps (strings) suitable for seeding another discovery round. On any
    failure (no model, unparseable reply) returns an empty-gaps result flagged as
    non-independent — callers must treat empty as UNKNOWN, not clean.
    """
    covered = "\n".join(
        f"- [{f.verdict.value if f.verdict else 'unverified'}] {f.claim} ({f.locator or 'no locator'})"
        for f in findings[:80]
    ) or "(no findings recorded)"
    caps = "\n".join(f"- {c}" for c in (caps_announced or [])) or "(none announced)"

    user = (
        f"TASK: {task}\n\n"
        f"FINDINGS SO FAR ({len(findings)} total, showing up to 80):\n{covered}\n\n"
        f"BOUNDS/CAPS ALREADY ANNOUNCED:\n{caps}\n\n"
        "Identify what is MISSING. Consider: a search modality never run; a region asserted clean "
        "without a stated reason; a claim accepted without an independent check; a source/file unread; "
        "an edge-case class not covered; an unfalsifiable load-bearing assumption silently trusted.\n\n"
        'Reply with ONLY JSON: {"gaps": ["<specific gap that could seed another round>", ...], '
        '"coverage_note": "<one-line honest assessment of coverage>"}'
    )

    messages = [{"role": "system", "content": _CRITIC_SYSTEM}, {"role": "user", "content": user}]
    try:
        text = aux_call(
            messages,
            model=model,
            temperature=0.2,
            main_runtime=runtime_from_agent(agent),
            call_fn=aux_call_fn,
        )
    except Exception as exc:  # never let the critic crash the run
        return CritiqueResult(gaps=[], coverage_note=f"critic unavailable: {exc}", independent=False)

    parsed = extract_json(text)
    if not isinstance(parsed, dict):
        return CritiqueResult(gaps=[], coverage_note="critic reply unparseable (treat as UNKNOWN, not clean)", raw=text)
    gaps = [str(g).strip() for g in parsed.get("gaps", []) if str(g).strip()]
    return CritiqueResult(
        gaps=gaps,
        coverage_note=str(parsed.get("coverage_note", "")).strip(),
        independent=False,
        raw=text,
    )
