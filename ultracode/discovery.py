"""Loop-until-dry discovery — for "find ALL of X" where the count is unknown.

Keep dispatching discovery rounds until K *consecutive* rounds surface nothing
new, deduping every round against a persistent seen-set so the loop converges
instead of re-finding the same things forever. Two stop conditions the doctrine
demanded beyond the upstream fixed-list approach:

  * DRY: K consecutive rounds with zero fresh findings (the classic).
  * DIMINISHING RETURNS: fresh-yield per round decays toward noise — a track
    that keeps returning near-duplicates resets the naive K-counter while adding
    nothing, so we also stop when the marginal yield flattens. (Watch the
    derivative, not just the level.)

Every bound is ANNOUNCED via the returned report (no silent caps). ``round_fn``
is injected (a thunk that runs one finder fan-out and returns its Findings), so
this controller is fully testable with scripted rounds and no model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ultracode.config import UltracodeConfig
from ultracode.schema import Finding, dedupe_findings


@dataclass
class DiscoveryReport:
    findings: List[Finding] = field(default_factory=list)
    rounds_run: int = 0
    fresh_per_round: List[int] = field(default_factory=list)
    stop_reason: str = ""
    caps_announced: List[str] = field(default_factory=list)


def discover(
    round_fn: Callable[[int, List[Finding]], List[Finding]],
    *,
    config: Optional[UltracodeConfig] = None,
    seen_keys: Optional[set] = None,
) -> DiscoveryReport:
    """Run loop-until-dry discovery.

    ``round_fn(round_index, known_findings)`` runs one discovery round and returns
    its raw Findings (may contain duplicates of prior rounds — we dedup). It gets
    the running known set so a finder can be told "don't re-report these".
    """
    cfg = config or UltracodeConfig()
    seen = seen_keys if seen_keys is not None else set()
    accumulated: List[Finding] = []
    report = DiscoveryReport()
    dry_streak = 0

    for r in range(cfg.discovery_max_rounds):
        raw = round_fn(r, list(accumulated)) or []
        fresh = [f for f in dedupe_findings(raw) if f.dedup_key() not in seen]
        for f in fresh:
            seen.add(f.dedup_key())
        accumulated.extend(fresh)
        report.rounds_run = r + 1
        report.fresh_per_round.append(len(fresh))

        if len(fresh) == 0:
            dry_streak += 1
        else:
            dry_streak = 0

        # honor the hard ceiling on total findings, announced
        if len(accumulated) >= cfg.max_findings:
            report.caps_announced.append(
                f"discovery hit max_findings={cfg.max_findings} after round {r + 1}; remaining surface NOT explored"
            )
            report.stop_reason = "max_findings"
            break

        if dry_streak >= cfg.discovery_dry_rounds:
            report.stop_reason = f"dry: {dry_streak} consecutive empty rounds"
            break

        if _diminishing(report.fresh_per_round, cfg):
            report.stop_reason = "diminishing returns: marginal yield flattened"
            report.caps_announced.append(
                f"stopped on diminishing returns after round {r + 1}; long tail declared residual risk"
            )
            break
    else:
        report.stop_reason = f"max_rounds={cfg.discovery_max_rounds} reached"
        report.caps_announced.append(
            f"discovery stopped at max_rounds={cfg.discovery_max_rounds}; surface may not be exhausted"
        )

    report.findings = dedupe_findings(accumulated)
    return report


def _diminishing(fresh_per_round: List[int], cfg: UltracodeConfig) -> bool:
    """True when the last few rounds are a positive-but-shrinking TRICKLE.

    Clean separation of duties: consecutive *zeros* are the dry detector's job;
    this detector handles the other tail — rounds that keep returning one or two
    near-duplicates forever (which reset the naive dry counter while adding
    nothing). So it only fires on a non-zero last round, after >=4 rounds, when
    the last three are each a shrinking trickle summing to <=2. Conservative, so
    a genuinely productive search is never cut short.
    """
    if len(fresh_per_round) < 4 or fresh_per_round[-1] == 0:
        return False
    first = fresh_per_round[0] or 1
    tail = fresh_per_round[-3:]
    return all(0 < x < first for x in tail) and sum(tail) <= 2
