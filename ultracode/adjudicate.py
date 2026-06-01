"""adjudicate.py — turn a false-positive machine into an accurate one.

The verification upgrade for IMPORTANT code. A skeptic VOTE is cheap and shares
the finder's blind spots; adjudication forces the steps a careful auditor does:
expand the context to the WHOLE file (so cross-file guards are visible), trace the
source->sink path, demand that NO mitigating guard sits on it, name the attacker
and the trust boundary actually crossed — and put the BURDEN OF PROOF on the
finding (false-positive until proven). This is what killed 8/12 hermes false
positives when Claude did it by hand.

Composes with: execution-arbiter (run a repro where testable) and a stronger
verify backend (break correlated errors). Adjudication is the reasoning gate;
execution is the ground-truth gate; the strong model is the reliability gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ultracode.adapters import aux_call, extract_json, runtime_from_agent
from ultracode.schema import Finding, Verdict


@dataclass
class Adjudication:
    verdict: str = "false_positive"   # real | conditional | false_positive | needs_context
    attacker: str = ""
    exploit_path: str = ""
    guards_found: str = ""
    trust_boundary_crossed: bool = False
    true_severity: str = ""
    precondition: str = ""
    confidence: float = 0.0
    reasoning: str = ""


_ADJ_SYSTEM = (
    "You are adjudicating whether a claimed code finding is a REAL, exploitable defect or a FALSE POSITIVE. "
    "The BURDEN OF PROOF is on the finding: treat it as a FALSE POSITIVE unless you can establish ALL of: "
    "(1) ATTACKER — who controls the relevant input, and how; "
    "(2) SOURCE->SINK PATH — trace the untrusted input to the dangerous operation; "
    "(3) NO MITIGATING GUARD on that path — read the WHOLE file and any obvious helpers; if a validator, "
    "allowlist, auth/permission check, escaping, or approval gate neutralizes it, it is NOT exploitable; "
    "(4) TRUST BOUNDARY actually crossed — a single-principal local-only path (e.g. a stdio CLI/editor with "
    "no second actor) crosses no boundary, so 'missing authz' there is not a vulnerability. "
    "Most flagged patterns ('tainted input reaches a function', 'substring check', 'no None check') are NOT "
    "exploitable once traced. Be ruthless and HONEST. IMPORTANT — three outcomes, not two: if the issue is "
    "GENUINELY REAL but only exploitable under specific PRECONDITIONS (operator misconfig, a niche deploy) or "
    "its severity was overstated, return 'conditional' and KEEP it (state the precondition + the corrected "
    "severity) — do NOT discard a real-but-gated bug as false_positive. Use 'false_positive' only when there "
    "is no real defect at all; 'needs_context' when you genuinely can't tell without code you can't see."
)


def adjudicate_finding(
    finding: Finding,
    file_text: str,
    *,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    agent: Any = None,
    model: Optional[str] = None,
) -> Adjudication:
    user = (
        f"CLAIMED FINDING ({finding.severity}): {finding.claim}\n"
        f"LOCATION: {finding.locator}\n"
        f"EVIDENCE OFFERED: {finding.evidence or '(none)'}\n\n"
        f"FULL FILE (read it — the guards may be elsewhere in here):\n{file_text[:24000]}\n\n"
        "Adjudicate per the burden of proof.\n"
        'Reply with ONLY JSON: {"verdict":"real|conditional|false_positive|needs_context", '
        '"attacker":"<who controls the input, or none>", '
        '"exploit_path":"<source->sink trace, or why none exists>", '
        '"guards_found":"<mitigations on the path, or none>", '
        '"trust_boundary_crossed":true|false, "true_severity":"critical|high|medium|low|info", '
        '"precondition":"<for conditional: what must be true to exploit>", '
        '"confidence":0.0-1.0, "reasoning":"<one-paragraph>"}'
    )
    try:
        text = aux_call(
            [{"role": "system", "content": _ADJ_SYSTEM}, {"role": "user", "content": user}],
            model=model, temperature=0.1, max_tokens=1500,
            main_runtime=runtime_from_agent(agent), call_fn=aux_call_fn,
        )
    except Exception:
        return Adjudication(verdict="needs_context", reasoning="adjudicator unavailable")
    p = extract_json(text)
    if not isinstance(p, dict):
        return Adjudication(verdict="needs_context", reasoning="adjudicator reply unparseable")
    verdict = str(p.get("verdict", "false_positive")).strip().lower()
    if verdict not in ("real", "conditional", "false_positive", "needs_context"):
        verdict = "needs_context"
    return Adjudication(
        verdict=verdict, attacker=str(p.get("attacker", "")).strip(),
        exploit_path=str(p.get("exploit_path", "")).strip(),
        guards_found=str(p.get("guards_found", "")).strip(),
        trust_boundary_crossed=bool(p.get("trust_boundary_crossed", False)),
        true_severity=str(p.get("true_severity", "")).strip().lower(),
        precondition=str(p.get("precondition", "")).strip(),
        confidence=float(p.get("confidence", 0.0) or 0.0),
        reasoning=str(p.get("reasoning", "")).strip(),
    )


def adjudicate_findings(
    findings: List[Finding],
    read_file_fn: Callable[[str], str],
    *,
    aux_call_fn=None, agent=None, model=None,
    only_severities=("critical", "high", "medium"),
) -> dict:
    """Adjudicate each load-bearing finding with full-file context + burden of
    proof. A finding SURVIVES only if verdict == 'real'. Returns counts. This is
    the accuracy gate — it converts a noisy candidate list into a defensible one.
    Best run on a STRONGER model than the finders (pass it via aux_call_fn)."""
    kept = conditional = dropped = unsure = 0
    for f in findings:
        if (f.severity or "").lower() not in only_severities:
            continue
        path = f.locator.split(":")[0]
        try:
            text = read_file_fn(path)
        except Exception:
            text = ""
        adj = adjudicate_finding(f, text, aux_call_fn=aux_call_fn, agent=agent, model=model)
        f.raw = dict(f.raw or {})
        f.raw["adjudication"] = adj.__dict__
        if adj.verdict == "real":
            f.survived = True
            f.verdict = Verdict.CONFIRMED
            kept += 1
        elif adj.verdict == "conditional":
            # real but precondition-gated/overstated -> KEEP it, flagged, with corrected severity
            f.survived = True
            f.verdict = Verdict.PARTIAL
            if adj.true_severity in ("critical", "high", "medium", "low", "info"):
                f.severity = adj.true_severity
            conditional += 1
        elif adj.verdict == "false_positive":
            f.survived = False
            f.verdict = Verdict.REFUTED
            dropped += 1
        else:  # needs_context -> keep but flag (don't assert, don't hide)
            f.verdict = Verdict.PARTIAL
            unsure += 1
        f.validate()
    return {"kept_real": kept, "conditional": conditional,
            "dropped_false_positive": dropped, "needs_context": unsure}
