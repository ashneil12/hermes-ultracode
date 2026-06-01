"""Data contracts for the ultracode harness.

Pure stdlib (dataclasses + enums) so the package imports anywhere and every
stage result is JSON-serializable for the run ledger. We deliberately do NOT
use pydantic here: the harness must stay importable in minimal environments,
and ``validate()`` + ``from_dict()`` give us the rejection discipline the
upstream PRs skipped (they ``str()``-coerced non-conforming child output).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OrchestrationShape(str, Enum):
    """The move ultracode selects for a task. ``SOLO`` is the restraint option:
    most turns should pick it. The rest are composed, not mutually exclusive."""

    SOLO = "solo"
    PARALLEL_FANOUT = "parallel_fanout"
    PIPELINE = "pipeline"
    BARRIER_MERGE = "barrier_merge"
    JUDGE_PANEL = "judge_panel"
    LOOP_UNTIL_DRY = "loop_until_dry"
    MULTI_MODAL_SWEEP = "multi_modal_sweep"
    TOURNAMENT = "tournament"
    STAGED_ESCALATION = "staged_escalation"
    MAP_REDUCE = "map_reduce"
    RECURSIVE = "recursive"


class Verdict(str, Enum):
    """A verifier's judgment on a finding. ``REFUTED`` is the default under
    uncertainty — the whole point of adversarial verification."""

    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    REFUTED = "refuted"


class VerifyLens(str, Enum):
    """The failure-lens a skeptic looks through. Diversity of lens catches
    failure modes that N identical yes-men never would."""

    CORRECTNESS = "correctness"
    SECURITY = "security"
    REPRODUCES = "reproduces"
    COMPLETENESS = "completeness"
    PERFORMANCE = "performance"
    STYLE = "style"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str, limit: int = 48) -> str:
    s = _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")
    return s[:limit] or "x"


@dataclass
class VerifierVote:
    """One skeptic's vote against a finding."""

    lens: VerifyLens
    verdict: Verdict
    rationale: str = ""
    # True when the skeptic believes the finding does NOT hold. Defaulting to
    # refuted-on-uncertainty is enforced by the verifier, not here.
    refuted: bool = True

    def validate(self) -> "VerifierVote":
        if not isinstance(self.lens, VerifyLens):
            self.lens = VerifyLens(str(self.lens))
        if not isinstance(self.verdict, Verdict):
            self.verdict = Verdict(str(self.verdict))
        self.refuted = self.verdict == Verdict.REFUTED
        return self

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["lens"] = self.lens.value
        d["verdict"] = self.verdict.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VerifierVote":
        return cls(
            lens=VerifyLens(d["lens"]),
            verdict=Verdict(d["verdict"]),
            rationale=d.get("rationale", ""),
            refuted=bool(d.get("refuted", d.get("verdict") == Verdict.REFUTED.value)),
        ).validate()


@dataclass
class Finding:
    """A candidate claim produced by a finder, then judged by a skeptic pool.

    ``survived`` is only meaningful after verification; ``verdict`` is the
    aggregate (majority) verdict. ``dedup_key`` lets us discard duplicates
    across finders and — critically — across discovery rounds, so loop-until-dry
    converges instead of re-surfacing the same thing forever.
    """

    claim: str
    evidence: str = ""
    locator: str = ""  # file:line, URL, or other addressable anchor
    severity: str = "info"  # info | low | medium | high | critical
    source_label: str = ""  # which finder/lens produced it
    raw: Dict[str, Any] = field(default_factory=dict)
    verdict: Optional[Verdict] = None
    votes: List[VerifierVote] = field(default_factory=list)
    survived: Optional[bool] = None

    def validate(self) -> "Finding":
        if not isinstance(self.claim, str) or not self.claim.strip():
            raise ValueError("Finding.claim must be a non-empty string")
        if self.verdict is not None and not isinstance(self.verdict, Verdict):
            self.verdict = Verdict(str(self.verdict))
        self.votes = [v.validate() for v in self.votes]
        return self

    def dedup_key(self) -> str:
        """Stable identity for dedup. Uses locator when present (most precise),
        else a hash of the normalized claim. Includes a POLARITY bit so a claim and
        its negation ("X is safe" / "X is not safe") never collapse — the 24-char slug
        truncates before a trailing 'not', and 'not'/'no' are stopwords, so without this
        a contradiction would be silently deduped away."""
        pol = "neg" if _polarity(self.claim) else "pos"
        if self.locator.strip():
            return f"loc::{self.locator.strip().lower()}::{pol}::{_slug(self.claim, 24)}"
        digest = hashlib.sha1(_slug(self.claim, 200).encode()).hexdigest()[:16]
        return f"claim::{pol}::{digest}"

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value if self.verdict else None
        d["votes"] = [v.as_dict() for v in self.votes]
        d["dedup_key"] = self.dedup_key()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Finding":
        v = d.get("verdict")
        return cls(
            claim=d["claim"],
            evidence=d.get("evidence", ""),
            locator=d.get("locator", ""),
            severity=d.get("severity", "info"),
            source_label=d.get("source_label", ""),
            raw=d.get("raw", {}) or {},
            verdict=Verdict(v) if v else None,
            votes=[VerifierVote.from_dict(x) for x in d.get("votes", [])],
            survived=d.get("survived"),
        ).validate()


@dataclass
class SubtaskSpec:
    """A unit of delegated work. Maps directly onto a delegate_task ``tasks[]``
    item, plus an optional ``lens`` for verifier subtasks."""

    goal: str
    context: str = ""
    toolsets: Optional[List[str]] = None
    role: str = "leaf"  # 'leaf' | 'orchestrator'
    lens: Optional[VerifyLens] = None
    label: str = ""

    def validate(self) -> "SubtaskSpec":
        if not isinstance(self.goal, str) or not self.goal.strip():
            raise ValueError("SubtaskSpec.goal must be a non-empty string")
        if self.role not in ("leaf", "orchestrator"):
            self.role = "leaf"
        if self.lens is not None and not isinstance(self.lens, VerifyLens):
            self.lens = VerifyLens(str(self.lens))
        return self

    def to_delegate_task(self) -> Dict[str, Any]:
        """The exact shape delegate_task expects in its ``tasks`` list."""
        t: Dict[str, Any] = {"goal": self.goal}
        if self.context:
            t["context"] = self.context
        if self.toolsets is not None:
            t["toolsets"] = list(self.toolsets)
        if self.role and self.role != "leaf":
            t["role"] = self.role
        return t


@dataclass
class StageResult:
    """The output of one pipeline stage, carrying enough provenance for the
    ledger and the completeness critic to reason about coverage."""

    stage: str
    findings: List[Finding] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    # Announced bounds — NEVER silently cap. If we truncate, say so here.
    caps_announced: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "findings": [f.as_dict() for f in self.findings],
            "meta": self.meta,
            "caps_announced": self.caps_announced,
        }


_STOPWORDS = set(
    "the a an is are be of to in on for and or with via using that this it its which when where "
    "if then else not no yes can could would should may might will but as at by from into".split()
)


def _claim_sig(claim: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (claim or "").lower()) if len(w) > 2 and w not in _STOPWORDS}


def _loc_tokens(locator: str) -> set:
    return {w for w in re.findall(r"[a-z0-9_]+", (locator or "").lower()) if len(w) > 2}


# "without" deliberately excluded: it's usually non-negating in claims ("works without
# issues") and false-splits legitimate near-duplicate merges.
_NEG = re.compile(r"\b(not|no|never|cannot|can'?t|won'?t|doesn'?t|isn'?t|aren'?t|fails?|unable|lacks?|none|neither)\b|n't", re.I)


def _polarity(claim: str) -> bool:
    """Coarse claim polarity (odd # of negations => negated). Used to keep CONTRADICTORY
    findings distinct: "X works" and "X does NOT work" share every content token once
    'not'/'no' are stopworded, so claim-sig Jaccard would merge them — collapsing a real
    disagreement into one position. A polarity mismatch blocks the merge so the landscape
    synthesis can present both sides (CONTESTED) instead of silently dropping one."""
    return len(_NEG.findall(claim or "")) % 2 == 1


def reconcile_findings(findings: List[Finding], *, similarity: float = 0.6) -> List[Finding]:
    """Root-cause reconciliation: collapse near-duplicate findings (the same bug
    reported by multiple finders with different wording/locators). Conservative —
    merges only when claim-signatures are highly similar AND the findings
    reference an overlapping symbol/locator, so genuinely distinct bugs survive.
    This is the fix for the over-generation that hurt precision at scale."""
    out: List[Finding] = []
    for f in dedupe_findings(findings):  # exact dedup first
        fsig, floc = _claim_sig(f.claim), _loc_tokens(f.locator)
        merged = False
        for g in out:
            gsig, gloc = _claim_sig(g.claim), _loc_tokens(g.locator)
            union = fsig | gsig
            jac = (len(fsig & gsig) / len(union)) if union else 0.0
            shares_symbol = bool(floc & gloc) or not (floc or gloc)
            opposite = _polarity(f.claim) != _polarity(g.claim)  # contradiction: keep both
            if jac >= similarity and shares_symbol and not opposite:
                if f.evidence and f.evidence not in g.evidence:
                    g.evidence = (g.evidence + " | " + f.evidence).strip(" |")
                if _sev_rank(f.severity) > _sev_rank(g.severity):
                    g.severity = f.severity
                merged = True
                break
        if not merged:
            out.append(f)
    return out


_SEV_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _sev_rank(sev: str) -> int:
    return _SEV_ORDER.get((sev or "info").lower(), 0)


def dedupe_findings(findings: List[Finding]) -> List[Finding]:
    """Collapse duplicates by ``dedup_key``, keeping the first occurrence and
    merging evidence from later ones. Used both within a round (across finders)
    and across discovery rounds (the seen-set) so loop-until-dry terminates."""
    seen: Dict[str, Finding] = {}
    for f in findings:
        k = f.dedup_key()
        if k not in seen:
            seen[k] = f
        else:
            existing = seen[k]
            if f.evidence and f.evidence not in existing.evidence:
                existing.evidence = (existing.evidence + " | " + f.evidence).strip(" |")
    return list(seen.values())
