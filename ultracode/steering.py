"""steering.py — the task-level decision functions, encoded as code, not prose.

This is the gate that makes the doctrine BINDING: should we orchestrate at all,
which shape, how many agents, which verify lenses, do we loop-until-dry. The
session-level executive/conductor loop (ignition gate, evidence-driven DAG
rewriting, latency-hiding scheduler) is specified in DOCTRINE.md "Executive
Layer" and stubbed in conductor.py — this module is the per-run brain it spawns.

Everything here is deterministic and signal-driven so it is testable with no
model. The planner (planner.py) does the actual LLM decomposition; steering
decides whether to invoke it and how to shape the run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from ultracode.config import UltracodeConfig
from ultracode.schema import OrchestrationShape, VerifyLens


class TurnClass:
    CONVERSATIONAL = "conversational"
    BUILD = "build"
    RESCOPE = "rescope"
    INVESTIGATE = "investigate"


# Signal vocabularies — the "tells" the doctrine reads. Kept small and honest;
# the planner refines. Each maps a tell to a shape bias.
# Enumeration INTENT, not incidental quantifiers: bare "all"/"each" match ordinary
# prose ("explain what each means", "all of this") and spuriously triggered a
# loop-until-dry shape on closed-form questions. Require a real find-all phrasing.
_FIND_ALL = re.compile(
    r"\b(find all|list all|all the|every\s+\w+|each of|enumerate|exhaustive|find every|all instances|all occurrences)\b",
    re.I)
_DEBUG = re.compile(r"\b(bug|broken|fails?|failing|crash|error|why does|root cause|regress)\b", re.I)
_AUDIT = re.compile(r"\b(review|audit|vulnerab|security|inspect|check the|analy[sz]e)\b", re.I)
_DESIGN = re.compile(r"\b(design|architecture|approach|should we|vs\.?|tradeoff|choose|which)\b", re.I)
_RESEARCH = re.compile(r"\b(research|investigate|compare|sources?|fact-?check|find out)\b", re.I)
_TRIVIAL = re.compile(r"^\s*(hi|hey|thanks|thank you|ok|okay|yes|no|continue|cool|got it)\b[.!]*\s*$", re.I)
_VERB = re.compile(r"\b(find|fix|build|write|implement|analy[sz]e|review|audit|debug|research|optimi[sz]e|migrate|refactor)\b", re.I)


@dataclass
class Decision:
    orchestrate: bool
    shape: OrchestrationShape
    n_finders: int
    lenses: List[VerifyLens]
    loop_until_dry: bool
    verify: bool
    reason: str
    signals: List[str] = field(default_factory=list)


def classify_turn(text: str) -> str:
    """The ignition gate's turn-typer. Conversational turns get zero machinery."""
    t = (text or "").strip()
    if not t or _TRIVIAL.match(t) or len(t) < 12:
        return TurnClass.CONVERSATIONAL
    if _DEBUG.search(t) or _RESEARCH.search(t):
        return TurnClass.INVESTIGATE
    return TurnClass.BUILD


def _detect_signals(task: str) -> List[str]:
    sig = []
    if _FIND_ALL.search(task):
        sig.append("find_all")
    if _DEBUG.search(task):
        sig.append("debug")
    if _AUDIT.search(task):
        sig.append("audit")
    if _DESIGN.search(task):
        sig.append("design")
    if _RESEARCH.search(task):
        sig.append("research")
    if _VERB.search(task):
        sig.append("action_verb")
    return sig


def decide(
    task: str,
    config: Optional[UltracodeConfig] = None,
    *,
    force_orchestrate: Optional[bool] = None,
) -> Decision:
    """Encode should_orchestrate / choose_shape / how_many / lenses / loop.

    The doctrine's restraint rule is the default: stay solo unless the task shows
    a genuine multi-unit or multi-lens signal. ``force_orchestrate`` overrides the
    gate (used by the benchmark to compare modes, and by an explicit /ultracode).
    """
    cfg = config or UltracodeConfig()
    signals = _detect_signals(task)
    turn = classify_turn(task)

    # should_orchestrate: a genuine multi-lens / multi-unit / unbounded-count signal.
    multi_signal = any(s in signals for s in ("find_all", "debug", "audit", "design", "research"))
    orchestrate = bool(multi_signal and turn != TurnClass.CONVERSATIONAL)
    if cfg.solo_by_default and not multi_signal:
        orchestrate = False
    if force_orchestrate is not None:
        orchestrate = force_orchestrate

    # choose_shape: map the dominant tell to a shape.
    if "find_all" in signals:
        shape = OrchestrationShape.LOOP_UNTIL_DRY
    elif "debug" in signals:
        shape = OrchestrationShape.MULTI_MODAL_SWEEP
    elif "design" in signals:
        shape = OrchestrationShape.JUDGE_PANEL
    elif "audit" in signals or "research" in signals:
        shape = OrchestrationShape.PARALLEL_FANOUT
    else:
        shape = OrchestrationShape.PARALLEL_FANOUT if orchestrate else OrchestrationShape.SOLO

    # how_many: bounded by config; debug/design lean fewer-but-orthogonal.
    if shape == OrchestrationShape.JUDGE_PANEL:
        n_finders = min(cfg.max_finders, 4)
    elif shape == OrchestrationShape.MULTI_MODAL_SWEEP:
        n_finders = min(cfg.max_finders, 4)
    else:
        n_finders = cfg.max_finders

    # which lenses: always at least correctness; add security for audit/security.
    lenses = list(cfg.verify_lenses)
    if "audit" not in signals and "debug" not in signals and VerifyLens.SECURITY in lenses and len(lenses) > 2:
        # for non-security tasks, don't waste a security skeptic — trim it
        lenses = [l for l in lenses if l != VerifyLens.SECURITY] or [VerifyLens.CORRECTNESS]

    loop = shape == OrchestrationShape.LOOP_UNTIL_DRY

    reason = (
        f"turn={turn}; signals={signals or ['none']}; "
        f"{'orchestrate' if orchestrate else 'SOLO (restraint: no multi-lens/unit signal)'}; "
        f"shape={shape.value}"
    )
    return Decision(
        orchestrate=orchestrate,
        shape=shape,
        n_finders=n_finders,
        lenses=lenses,
        loop_until_dry=loop,
        verify=cfg.verify and orchestrate,
        reason=reason,
        signals=signals,
    )
