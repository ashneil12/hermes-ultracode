#!/usr/bin/env python3
"""ultracode decision gate — the binding orchestrate/solo oracle.

Calls the user's real steering.decide() from ~/Projects/hermes-ultracode so the
decision is deterministic and reproducible, not eyeballed. Falls back to a
self-contained mini-gate if the harness isn't present, so the skill never breaks.

Usage:
    python3 gate.py "fix the login bug, it crashes on submit"
    echo "find all token leaks" | python3 gate.py
"""
from __future__ import annotations
import os
import sys
import re

def _find_harness():
    """Locate the ultracode engine. Search order (first hit wins):
      1. engine bundled WITH this skill (../../engine, relative to scripts/) — zero-setup
      2. the standalone harness repo at ~/Projects/hermes-ultracode (dev machine)
      3. ULTRACODE_HARNESS env override
    Returns a path that contains an importable `ultracode` package, or None.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("ULTRACODE_HARNESS", ""),
        os.path.normpath(os.path.join(here, "..", "..", "engine")),   # bundled (skill/../engine after install layout)
        os.path.normpath(os.path.join(here, "..", "engine")),          # alt layout
        os.path.expanduser("~/Projects/hermes-ultracode"),             # dev repo
    ]
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "ultracode")):
            return c
    return None

HARNESS = _find_harness()

# Trigger words that force MAXIMUM RIGOR regardless of the fan-out gate.
_FORCE = re.compile(
    r"\b(ultracode|ultrathink|megathink|go all in|build (it |this |everything )?out|maximum rigor|all in)\b",
    re.I,
)


def _read_task() -> str:
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    print("usage: gate.py \"<task text>\"", file=sys.stderr)
    sys.exit(2)


def _via_harness(task: str):
    if not HARNESS:
        raise ImportError("ultracode engine not found (bundled engine/ or ~/Projects/hermes-ultracode)")
    sys.path.insert(0, HARNESS)
    from ultracode.steering import decide  # type: ignore
    d = decide(task)
    return {
        "source": "harness",
        "orchestrate": d.orchestrate,
        "shape": d.shape.value,
        "n_finders": d.n_finders,
        "loop_until_dry": d.loop_until_dry,
        "lenses": [l.value for l in d.lenses],
        "reason": d.reason,
    }


def _fallback(task: str):
    t = task.lower()
    find_all = bool(re.search(r"\b(find all|list all|every \w+|all instances|exhaustive|enumerate)\b", t))
    debug = bool(re.search(r"\b(bug|crash|fails?|error|why does|root cause|regress)\b", t))
    audit = bool(re.search(r"\b(audit|vulnerab|security|review|inspect|analy[sz]e)\b", t))
    design = bool(re.search(r"\b(design|architecture|tradeoff|should we|vs\b|choose|which)\b", t))
    research = bool(re.search(r"\b(research|investigate|compare|sources?|fact.?check)\b", t))
    multi = find_all or debug or audit or design or research
    trivial = len(task.strip()) < 12 or re.match(r"^\s*(hi|hey|thanks|ok|yes|no|cool)\b", t)
    orchestrate = bool(multi and not trivial)
    shape = ("loop_until_dry" if find_all else "multi_modal_sweep" if debug
             else "judge_panel" if design else "parallel_fanout" if orchestrate else "solo")
    return {
        "source": "fallback",
        "orchestrate": orchestrate,
        "shape": shape,
        "n_finders": 5,
        "loop_until_dry": find_all,
        "lenses": ["correctness"] + (["security"] if audit else []),
        "reason": f"fallback gate; multi={multi}; trivial={bool(trivial)}",
    }


def _difficulty_override(task: str, context_chars: int, res: dict):
    """DISCERNMENT triage — the fix for the over-firing gate.

    steering.decide() orchestrates on an intent SIGNAL alone (find-all/audit/etc)
    without weighing whether the task is actually hard enough to need fan-out.
    Benchmarks (AXProbe, precision-audit) proved baseline single-pass TIES the
    full harness at 9-25x less cost whenever the task is within single-shot reach.

    So: even when decide() says orchestrate, stay SOLO unless the work is genuinely
    large/contested. Escalate only if EITHER:
      * the corpus is big enough to dilute single-pass attention
        (context_chars >= full_orchestration_min_chars, default 6000), OR
      * the task is an unbounded find-all over a large corpus
        (loop_until_dry AND big corpus), OR
      * stakes are explicitly high (precision/sign-off/security keywords) AND
        the corpus is non-trivial.
    This is "auto-scale rigor to input size/stakes" from ULTRACODE_REPORT's
    own next-steps list — the missing piece that makes ultracode beat naive.
    """
    if not res["orchestrate"]:
        return res, None
    # CONTESTED-CHOICE EXEMPTION: a judge-panel (design/pricing/which-approach) earns
    # its keep from INDEPENDENT FRAMINGS, not corpus coverage — so it is NOT size-gated.
    # A real tradeoff decision benefits from N drafts + graft even on tiny input.
    if res["shape"] == "judge_panel":
        return res, None
    MIN = 6000  # full_orchestration_min_chars
    big = context_chars >= MIN
    # high-stakes = EXPLICIT precision/sign-off language, NOT the audit/security verb
    # that merely triggered the gate (that verb is the signal, not the stakes).
    high_stakes = bool(re.search(r"\b(precision.critical|sign.?off|zero.false|production.gate|must not miss|exhaustive|do not miss)\b", task, re.I))
    loop_big = res["loop_until_dry"] and context_chars >= MIN * 2
    escalate = big or loop_big or (high_stakes and context_chars >= MIN // 2)
    if escalate:
        return res, None
    # downgrade to solo — the cheap path that ties on easy work
    downgraded = dict(res)
    downgraded["orchestrate"] = False
    downgraded["shape"] = "solo"
    downgraded["loop_until_dry"] = False
    return downgraded, (
        f"DISCERNMENT: signal present but task is within single-shot reach "
        f"(context={context_chars}c < {MIN}; high_stakes={high_stakes}). "
        f"Stay SOLO — orchestration would tie at higher cost (verified by benchmark)."
    )


def main():
    task = _read_task()
    context_chars = int(os.environ.get("ULTRACODE_CONTEXT_CHARS", "0"))
    try:
        res = _via_harness(task)
    except Exception as e:
        res = _fallback(task)
        res["reason"] += f" (harness unavailable: {type(e).__name__})"
    forced = bool(_FORCE.search(task))
    res, override = _difficulty_override(task, context_chars, res)
    print(f"task         : {task[:80]}")
    print(f"source       : {res['source']}")
    print(f"context_chars: {context_chars}  (set ULTRACODE_CONTEXT_CHARS for difficulty gate)")
    print(f"orchestrate  : {res['orchestrate']}")
    print(f"shape        : {res['shape']}")
    print(f"n_finders    : {res['n_finders']}")
    print(f"loop_til_dry : {res['loop_until_dry']}")
    print(f"verify_lenses: {res['lenses']}")
    print(f"force_max_rigor: {forced}  (explicit trigger word -> xhigh effort + full verify)")
    print(f"reason       : {res['reason']}")
    if override:
        print(f"DISCERNMENT  : {override}")
    if forced and not res["orchestrate"]:
        print("note         : gate says SOLO but trigger word forces MAXIMUM RIGOR (solo + xhigh + ground-truth-once).")


if __name__ == "__main__":
    main()
