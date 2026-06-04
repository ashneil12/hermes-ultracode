"""Adversarial verification — the cognitive core, and the thing no upstream PR has.

The stance, straight from the doctrine: for each load-bearing finding, spawn K
*independent* skeptics, each looking through a DIFFERENT failure-lens, each
instructed to REFUTE and to default the verdict to ``refuted`` under uncertainty.
A finding survives only on a quorum of confirmations. Two refinements the
distillation insisted on:

  * KILL THE KILLER — a refutation must itself state a mechanism; a skeptic that
    says "looks wrong" without a reason is as suspect as a finder that says
    "looks fine". This protects a correct front-runner from a miscalibrated kill.
  * REPORTS ARE TESTIMONY, NOT FACT — a skeptic that asserts a verdict with no
    rationale/evidence is downgraded to ``refuted`` (uncertain), because the most
    dangerous unaudited input is the orchestrator believing its own workers.

Concurrency is a SIBLING delegate fan-out (one subagent per finding×lens), never
threaded ``call_llm`` — see CONTRACTS.md §2 (call_llm's routing globals are not
thread-safe) and §1 (verifiers as siblings dodge the depth=1 nesting cap).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from ultracode.adapters import delegate_fanout, extract_json
from ultracode.config import UltracodeConfig
from ultracode.kinds import TaskKind, skeptic_instruction
from ultracode.schema import Finding, Verdict, VerifyLens, VerifierVote

_LENS_BRIEF = {
    VerifyLens.CORRECTNESS: "Does the logic actually hold? State the causal chain end to end. If you cannot, it is refuted.",
    VerifyLens.SECURITY: "Is this exploitable / unsafe in the way claimed, or does the claim overstate/understate the risk? Reachability matters.",
    VerifyLens.REPRODUCES: "Does this actually reproduce / is the evidence real? Would the cited fact survive someone re-running it? Unreproducible => refuted.",
    VerifyLens.COMPLETENESS: "Does the claim's explanation predict EXACTLY the observed set — no unexplained survivors, no unexplained collateral?",
    VerifyLens.PERFORMANCE: "Is the measurement valid (mean vs p99, warm vs cold, within noise)? A within-noise delta is refuted.",
    VerifyLens.STYLE: "Is this a real defect or a cosmetic nit dressed up as one? Demote cosmetics.",
}


def _skeptic_prompt(finding: Finding, lens: VerifyLens, context: str = "", directive: str = "") -> str:
    material = f"\nMATERIAL TO CHECK THE CLAIM AGAINST (ground truth — read it, do not guess):\n{context}\n" if context else ""
    check = f"WHAT TO CHECK (decided for this task): {directive}\n" if directive else ""
    return (
        f"You are an adversarial verifier. Your job is to REFUTE the claim below, not to confirm it.\n"
        f"{check}"
        f"LENS: {lens.value} — {_LENS_BRIEF.get(lens, 'Attack the claim on its merits.')}\n"
        f"{material}\n"
        f"CLAIM: {finding.claim}\n"
        f"EVIDENCE OFFERED: {finding.evidence or '(none given)'}\n"
        f"LOCATOR: {finding.locator or '(none)'}\n\n"
        "Rules:\n"
        "1. DEFAULT TO REFUTED. If you cannot establish the claim holds with a stated mechanism, your verdict is 'refuted'.\n"
        "2. KILL THE KILLER: if you refute, you must state the MECHANISM of the refutation — a bare 'seems wrong' is not allowed.\n"
        "3. Do not trust the offered evidence at face value; check it against ground truth where you can (read the locator, reason about the mechanism). Reasoning is not evidence — prefer to actually verify.\n"
        "4. Verdict 'confirmed' only if the claim holds for a stated, checkable reason. 'partial' if it holds in a narrowed form.\n\n"
        'Reply with ONLY a JSON object: {"verdict": "confirmed"|"partial"|"refuted", "rationale": "<mechanism, 1-3 sentences>"}'
    )


def _vote_from_result(entry: Dict[str, Any], lens: VerifyLens) -> VerifierVote:
    """Parse one skeptic's delegate-result entry into a vote.

    A vote only COUNTS (as a confirm or a kill) if it is a completed, parseable
    verdict WITH a stated mechanism — this enforces both 'reports are testimony'
    (non-completion / garble = UNKNOWN) and 'kill-the-killer' (a refutation must
    state its mechanism). Everything that doesn't count becomes PARTIAL = ABSTAIN:
    it neither confirms nor kills, so an UNKNOWN can't silently destroy a true
    finding (the asymmetric-rejection failure the doctrine warned about)."""
    def abstain(note: str) -> VerifierVote:
        return VerifierVote(lens, Verdict.PARTIAL, rationale=f"abstain: {note}").validate()

    if not isinstance(entry, dict) or entry.get("status") != "completed":
        return abstain("skeptic did not complete (UNKNOWN, not a kill)")
    parsed = extract_json(entry.get("summary") or "")
    if not isinstance(parsed, dict) or "verdict" not in parsed:
        return abstain("skeptic reply unparseable")
    raw_verdict = str(parsed.get("verdict", "")).strip().lower()
    rationale = str(parsed.get("rationale", "")).strip()
    try:
        verdict = Verdict(raw_verdict)
    except ValueError:
        return abstain(f"unknown verdict {raw_verdict!r}")
    # a confirm or a kill with no mechanism does not count — it abstains.
    if verdict in (Verdict.CONFIRMED, Verdict.REFUTED) and not rationale:
        return abstain("verdict asserted with no mechanism")
    return VerifierVote(lens, verdict, rationale=rationale).validate()


def verify_findings(
    findings: List[Finding],
    *,
    context: str = "",
    parent_agent: Any = None,
    config: Optional[UltracodeConfig] = None,
    lenses: Optional[List[VerifyLens]] = None,
    delegate_fn: Optional[Callable[..., str]] = None,
    toolsets: Optional[List[str]] = None,
    survival_mode: str = "defend",
    concurrency: Optional[int] = None,
    skeptic_directive: str = "",
) -> List[Finding]:
    """survival_mode:
    - "defend" (default, for FINDINGS that carry their own evidence): a finding
      survives UNLESS a quorum of skeptics refutes it WITH a mechanism. Protects
      true positives from miscalibrated kills (the doctrine's symmetric burden).
    - "prove" (for bare CLAIMS that carry no evidence): a claim survives ONLY IF a
      quorum of skeptics confirms it. Catches subtly-false claims a single pass
      would accept."""
    """Run the skeptic pool over ``findings`` and annotate each with votes,
    aggregate verdict, and ``survived``.

    Returns the SAME Finding objects, mutated with .votes/.verdict/.survived.
    A finding survives iff confirmed-votes >= quorum (majority by default).
    """
    cfg = config or UltracodeConfig()
    lenses = lenses or cfg.verify_lenses
    if not findings or not lenses:
        for f in findings:
            f.survived = True if not lenses else f.survived
        return findings

    # VOI triage: concentrate lenses where being wrong is costly. critical/high
    # get every lens; medium two; low/info one. Conservation of rigor — and a big
    # cost cut at scale (a 12-finding mix drops from 36 skeptics to ~half).
    def _lenses_for(severity: str) -> List[VerifyLens]:
        # VOI triage, but NEVER drop below 2 lenses: in defend mode a kill needs a
        # quorum, and a 1-lens finding could be killed by a SINGLE over-zealous
        # skeptic (the large-dense benchmark killed a real bug exactly this way).
        # critical/high get every lens; everything else gets 2 (kills still need 2).
        if not cfg.voi_verify:
            return lenses
        s = (severity or "info").strip().lower()
        if s in ("critical", "high") or len(lenses) <= 2:
            return lenses
        return lenses[:2]

    # Build one sibling subagent task per (finding, lens); track the mapping so
    # variable per-finding lens counts re-assemble correctly.
    tasks: List[Dict[str, Any]] = []
    task_map: List[tuple] = []  # (finding_index, lens)
    for fi, f in enumerate(findings):
        for lens in _lenses_for(f.severity):
            t: Dict[str, Any] = {"goal": _skeptic_prompt(f, lens, context, skeptic_directive)}
            if toolsets is not None:
                t["toolsets"] = list(toolsets)
            tasks.append(t)
            task_map.append((fi, lens))

    if not tasks:
        for f in findings:
            f.survived = True
        return findings

    results = delegate_fanout(
        tasks, parent_agent=parent_agent, role="leaf",
        max_children=cfg.max_children, concurrency=concurrency, delegate_fn=delegate_fn,
    )
    by_index: Dict[int, Dict[str, Any]] = {}
    for entry in results:
        if isinstance(entry, dict):
            by_index[int(entry.get("task_index", len(by_index)))] = entry

    votes_by_finding: Dict[int, List[VerifierVote]] = defaultdict(list)
    for i, (fi, lens) in enumerate(task_map):
        votes_by_finding[fi].append(_vote_from_result(by_index.get(i, {}), lens))

    for fi, finding in enumerate(findings):
        votes = votes_by_finding.get(fi, [])
        finding.votes = votes
        quorum = cfg.effective_quorum(len(votes)) if votes else 1  # majority of the lenses actually run
        confirms = sum(1 for v in votes if v.verdict == Verdict.CONFIRMED)
        kills = sum(1 for v in votes if v.verdict == Verdict.REFUTED)
        if survival_mode == "prove":
            finding.survived = confirms >= quorum
            finding.verdict = Verdict.CONFIRMED if finding.survived else Verdict.REFUTED
        else:  # "defend"
            # A finding (which carries its own evidence) survives unless its
            # refutation is UNANIMOUS — every lens that voted refuted it WITH a
            # mechanism. When the verifier itself is a weak model, a quorum can
            # be wrong; requiring unanimity protects real bugs from a miscalibrated
            # skeptic (recall priority) while still killing clear-cut spurious that
            # every lens agrees on.
            n_voting = len(votes)
            finding.survived = not (n_voting >= 2 and kills >= n_voting)
            if not finding.survived:
                finding.verdict = Verdict.REFUTED
            elif confirms >= 1:
                finding.verdict = Verdict.CONFIRMED
            else:
                finding.verdict = Verdict.PARTIAL  # survived but unverified — report with caveat
        finding.validate()
    return findings


def survivors(findings: List[Finding]) -> List[Finding]:
    """The findings that survived adversarial verification."""
    return [f for f in findings if f.survived]


def verify_to_convergence(
    findings: List[Finding],
    *,
    rounds: int = 1,
    config: Optional[UltracodeConfig] = None,
    on_round: Optional[Callable[[int, int, int], None]] = None,
    **verify_kw: Any,
) -> List[Finding]:
    """Iterated refutation (teknium's adversarial convergence). Run ``verify_findings`` up to ``rounds``
    times; after round 1, RE-CHALLENGE only the current survivors with a FRESH independent skeptic pass.
    A finding must survive EVERY round to be kept — one pass can rubber-stamp a plausible-but-wrong claim;
    independent re-refutation breaks that. Converges early when a round drops nothing new. Returns the
    SAME (mutated) finding objects; survivors are ``[f for f in findings if f.survived]``.

    ``on_round(round_index, n_challenged, n_survived)`` is an optional progress callback.
    """
    cfg = config or UltracodeConfig()
    rounds = max(1, int(rounds))
    verify_findings(findings, config=cfg, **verify_kw)  # round 1: challenge all
    alive = survivors(findings)
    if on_round:
        on_round(1, len(findings), len(alive))
    for r in range(2, rounds + 1):
        if not alive:
            break
        before = len(alive)
        verify_findings(alive, config=cfg, **verify_kw)  # fresh independent pass over survivors
        alive = survivors(alive)
        if on_round:
            on_round(r, before, len(alive))
        if len(alive) == before:
            break  # converged: a full round refuted nothing -> stable
    return findings
