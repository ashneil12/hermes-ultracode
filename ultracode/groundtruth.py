"""groundtruth.py — confirm a finding by RUNNING a repro, not by reasoning.

For a testable finding, ask the model to write a self-contained script that exits
0 IFF the bug reproduces, then execute it. The interpreter's exit code is the
verdict — the one truly independent verifier (the world), breaking the solver's
closed loop.

Design choice (safety + the symmetric-burden rule): a successful repro CONFIRMS
(adds hard positive evidence); a failed/absent repro only ANNOTATES "could not
reproduce" — it never KILLS a finding, because a weak model's bad repro must not
be allowed to discard a real bug. Execution is used to raise confidence, not to
manufacture false negatives.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ultracode.adapters import aux_call, runtime_from_agent
from ultracode.execute import ExecResult, extract_code, run_python
from ultracode.schema import Finding


_REPRO_SYSTEM = (
    "You write minimal, self-contained Python repro scripts. The script must include any needed code "
    "inline and use ONLY the standard library. CONTRACT: the script must `sys.exit(0)` if and only if the "
    "claimed bug genuinely reproduces (catch the expected error / assert the wrong behavior, then exit 0); "
    "otherwise raise or `sys.exit(1)`. Output ONLY the script, no prose, no fences."
)


def confirm_by_execution(
    finding: Finding,
    code: str,
    *,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    agent: Any = None,
    model: Optional[str] = None,
    run_fn: Callable[..., ExecResult] = run_python,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """Returns {reproduced: True|False|None, detail, exec}. None = couldn't run."""
    user = (
        f"CLAIMED BUG: {finding.claim}\n"
        f"LOCATION: {finding.locator}\n"
        f"EVIDENCE: {finding.evidence}\n\n"
        f"CODE UNDER TEST:\n{code}\n\n"
        "Write the repro per the contract: sys.exit(0) iff the bug reproduces."
    )
    try:
        reply = aux_call(
            [{"role": "system", "content": _REPRO_SYSTEM}, {"role": "user", "content": user}],
            model=model, temperature=0.2, max_tokens=2000,
            main_runtime=runtime_from_agent(agent), call_fn=aux_call_fn,
        )
    except Exception as exc:
        return {"reproduced": None, "detail": f"repro generation failed: {exc}", "exec": None}

    snippet = extract_code(reply)
    if not snippet:
        return {"reproduced": None, "detail": "no repro produced", "exec": None}
    res = run_fn(snippet, timeout=timeout)
    if res.timed_out:
        return {"reproduced": None, "detail": "repro timed out", "exec": res.as_dict()}
    # Execution is the verdict: exit 0 => the repro asserts the bug reproduces.
    reproduced = bool(res.ok)
    return {
        "reproduced": reproduced,
        "detail": "reproduced by execution" if reproduced else "did not reproduce (annotation only — not a kill)",
        "exec": res.as_dict(),
    }


def arbitrate_findings(
    findings,
    code: str,
    *,
    aux_call_fn=None, agent=None, model=None, run_fn=run_python,
    only_severities=("critical", "high", "medium"),
) -> dict:
    """Execution as the ARBITER of disputed verdicts. For each testable finding,
    run a repro; if it REPRODUCES, that is ground truth: confirm it, and if the
    skeptics had killed it, RESURRECT it (the runtime overrules an unreliable
    weak-model vote). A non-reproducing repro only annotates — it never kills,
    because absence-of-repro is weak evidence (the repro itself may be wrong).
    This recovers recall lost to false refutations. Returns counts."""
    from ultracode.schema import Verdict

    confirmed = resurrected = 0
    for f in findings:
        if (f.severity or "").lower() not in only_severities:
            continue
        gt = confirm_by_execution(f, code, aux_call_fn=aux_call_fn, agent=agent, model=model, run_fn=run_fn)
        f.raw = dict(f.raw or {})
        f.raw["ground_truth"] = gt
        if gt.get("reproduced") is True:
            confirmed += 1
            if not f.survived:
                f.survived = True
                f.verdict = Verdict.CONFIRMED
                f.raw["arbiter"] = "RESURRECTED: reproduced by execution despite skeptic refutation"
                resurrected += 1
            else:
                f.raw["arbiter"] = "confirmed by execution"
            f.validate()
    return {"confirmed": confirmed, "resurrected": resurrected}


def ground_truth_pass(
    findings,
    code: str,
    *,
    aux_call_fn=None, agent=None, model=None, run_fn=run_python,
    only_severities=("critical", "high", "medium"),
) -> int:
    """Annotate findings with execution-based confirmation. Confirms (boosts) but
    never kills. Returns the count of findings confirmed by actually running."""
    confirmed = 0
    for f in findings:
        if (f.severity or "").lower() not in only_severities:
            continue
        gt = confirm_by_execution(f, code, aux_call_fn=aux_call_fn, agent=agent, model=model, run_fn=run_fn)
        f.raw = dict(f.raw or {})
        f.raw["ground_truth"] = gt
        if gt.get("reproduced") is True:
            confirmed += 1
    return confirmed
