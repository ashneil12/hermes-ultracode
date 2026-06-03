"""UltracodeConfig — the knobs, and a loader that reads them from Hermes config.

Defaults encode the ultracode stance: xhigh effort, adversarial verification on
by default, loop-until-dry with a 2-empty-round termination, and a conservative
scale-to-the-ask gate (default solo). Every cap here is meant to be ANNOUNCED
when it bites — see ``announce_caps``.

Config precedence: explicit kwargs > Hermes config.yaml (``ultracode:`` section,
falling back to ``delegation:`` for concurrency) > these defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultracode.schema import VerifyLens

# The literal effort level we drive to. "xhigh" is already valid in
# VALID_REASONING_EFFORTS and on-budget for Opus 4.7+ (4.6 maps xhigh->max).
DEFAULT_EFFORT = "xhigh"


@dataclass
class UltracodeConfig:
    # -- reasoning --
    effort: str = DEFAULT_EFFORT

    # -- orchestration caps (announced when hit) --
    max_children: int = 3          # delegate concurrency per wave (fork cap)
    max_finders: int = 6           # finder pool size for discovery
    max_findings: int = 200        # hard ceiling on findings carried forward
    reconcile: bool = True         # root-cause dedup: merge near-duplicate findings (same bug, different wording) — fixes over-generation hurting precision

    # -- adversarial verification --
    verify: bool = True
    verify_lenses: List[VerifyLens] = field(
        default_factory=lambda: [
            VerifyLens.CORRECTNESS,
            VerifyLens.SECURITY,
            VerifyLens.REPRODUCES,
        ]
    )
    verify_quorum: int = 2         # votes-to-survive out of len(lenses)
    verify_default_refuted: bool = True  # the stance: uncertain -> refuted
    voi_verify: bool = True        # VOI triage: concentrate lenses where being wrong is costly (critical/high -> all, medium -> 2, low/info -> 1) — conservation of rigor, and a big cost cut at scale
    execution_verify: bool = False # ground-truth-once: RUN a repro to confirm findings (the only true exit from the closed loop). OFF by default — runs model-generated code; enable only for trusted/benchmark targets or behind a real sandbox
    execution_assist: bool = False # execution as a REASONING aid: for search/enumeration/simulation/exact-arithmetic tasks, let the agent WRITE+RUN a program to compute the answer (the biggest cognitive lever for a weak model). The agent declines for pure-reasoning tasks. OFF by default (runs model code; enable for trusted/benchmark or behind a sandbox)

    # -- loop-until-dry discovery --
    discovery_max_rounds: int = 6
    discovery_dry_rounds: int = 2  # stop after K consecutive empty rounds
    reactive_replan: bool = True   # re-DERIVE the work-list from findings each round (emergent decomposition) rather than re-run the same finders
    streaming_discovery: Optional[bool] = None  # NO-BARRIER discovery: spawn follow-up finders ON THE FLY the instant a result warrants it (pipeline.run_reactive), instead of waiting for a whole round. None = AUTO (on when a concurrency-safe backend is configured, where parallel on-the-fly spawning is a real win; off on the serial thread-unsafe default to keep the cheap per-round cost profile). True/False force it.

    # -- orchestration scale (in-flight agents). None = sequential waves (real-Hermes-safe).
    # A concurrency-safe backend (DeepSeek client / patched Hermes core) can set this to 100+.
    concurrency: Optional[int] = None

    # -- scale-to-the-ask --
    solo_by_default: bool = True   # restraint: orchestrate only on a real signal
    discernment: bool = True       # DISCERNMENT: solo-first, escalate to orchestration only if a quick triage says it would materially help (the fix for "always full-metal")
    full_orchestration_min_chars: int = 6000  # FULL (loop-until-dry) is reserved for genuinely large find-all work; smaller tasks that warrant orchestration get the cheap LIGHT ensemble

    # -- deep research (research-kind only; defaults preserve code behavior) --
    research_landscape_synth: bool = True   # organize the answer BY FACET preserving every specific, instead of lead-with-one-result (which collapses the per-facet depth a fan-out paid for)
    # NOTE: contradiction preservation is handled inline in reconcile_findings (a polarity
    # guard keeps opposite claims distinct) — no separate detect pass / flag needed. A
    # research fact-check gate was considered and dropped as redundant with the post-loop
    # verify pass (see ULTRACODE_REPORT.md hardening YAGNI list).

    # -- budget (token ceiling; None = no object, but still announced) --
    run_budget_tokens: Optional[int] = None

    # -- behavior --
    announce_caps: bool = True     # never silently truncate/cap

    def lenses_for(self, n: Optional[int] = None) -> List[VerifyLens]:
        """The verification lenses to use, optionally trimmed to ``n``."""
        lenses = list(self.verify_lenses)
        if n is not None:
            lenses = lenses[: max(1, n)]
        return lenses

    def effective_quorum(self, n_lenses: int) -> int:
        """Majority by default, never more than the lenses we actually ran."""
        return max(1, min(self.verify_quorum, n_lenses))


def load_ultracode_config(cfg: Optional[Dict[str, Any]] = None, **overrides: Any) -> UltracodeConfig:
    """Build an UltracodeConfig from Hermes config + explicit overrides.

    ``cfg`` is a loaded Hermes config dict; if None we load it lazily. We never
    raise on a missing section — ultracode runs on defaults out of the box.
    """
    base = UltracodeConfig()
    cfg = _maybe_load_config(cfg)
    if cfg:
        _get = _cfg_getter(cfg)
        base.effort = _get("ultracode", "effort", default=base.effort) or base.effort
        base.max_children = int(
            _get("ultracode", "max_children",
                 default=_get("delegation", "max_concurrent_children", default=base.max_children))
        )
        base.max_finders = int(_get("ultracode", "max_finders", default=base.max_finders))
        base.verify = bool(_get("ultracode", "verify", default=base.verify))
        base.verify_quorum = int(_get("ultracode", "verify_quorum", default=base.verify_quorum))
        base.discovery_dry_rounds = int(_get("ultracode", "discovery_dry_rounds", default=base.discovery_dry_rounds))
        base.discovery_max_rounds = int(_get("ultracode", "discovery_max_rounds", default=base.discovery_max_rounds))
        base.solo_by_default = bool(_get("ultracode", "solo_by_default", default=base.solo_by_default))
        rb = _get("ultracode", "run_budget_tokens", default=base.run_budget_tokens)
        base.run_budget_tokens = int(rb) if rb else None
        lenses = _get("ultracode", "verify_lenses", default=None)
        if isinstance(lenses, list) and lenses:
            base.verify_lenses = [VerifyLens(str(x)) for x in lenses]

    for k, v in overrides.items():
        if hasattr(base, k) and v is not None:
            setattr(base, k, v)
    return base


def _maybe_load_config(cfg: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if cfg is not None:
        return cfg
    try:
        from hermes_cli.config import load_config  # type: ignore

        return load_config()
    except Exception:
        return None


def _cfg_getter(cfg: Dict[str, Any]):
    """Prefer the fork's safe nested getter; fall back to a local traversal."""
    try:
        from hermes_cli.config import cfg_get  # type: ignore

        return lambda *keys, default=None: cfg_get(cfg, *keys, default=default)
    except Exception:
        def _get(*keys: str, default: Any = None) -> Any:
            cur: Any = cfg
            for key in keys:
                if not isinstance(cur, dict) or key not in cur:
                    return default
                cur = cur[key]
            return cur if cur is not None else default

        return _get
