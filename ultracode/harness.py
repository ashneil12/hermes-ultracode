"""harness.py — the ultracode run() entry. Steer -> plan -> find(loop) -> verify
-> critic -> synthesize, composing every module into one deterministic loop.

This is what the benchmark drives. Two DI seams (``delegate_fn`` for the parallel
finder/skeptic fan-out, ``aux_call_fn`` for the tools-off plan/critic/synthesize
calls) let the whole thing run against ANY backend — the real Hermes runtime, or
the DeepSeek client the benchmark injects, or fakes in tests.

The structure IS the value: a weak model wrapped in decompose -> fan-out ->
adversarially-verify -> loop-until-dry -> synthesize should beat the same weak
model answering in one shot — IF the instructions are operational, not lazy. The
benchmark exists to prove that, and to expose laziness the moment the weak model
finds the gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ultracode.adapters import aux_call, delegate_fanout, extract_json, runtime_from_agent
from ultracode.config import UltracodeConfig
from ultracode.critic import completeness_critic
from ultracode.discovery import discover
from ultracode.ledger import RunLedger
from ultracode.schema import Finding, StageResult, dedupe_findings, reconcile_findings
from ultracode.steering import Decision, decide
from ultracode.planner import Approach, Plan, plan as make_plan, plan_approach, replan_for_gaps
from ultracode.triage import assess
from ultracode.kinds import (
    TaskKind, classify_kind, research_depth_directive, skeptic_instruction, worker_instruction,
)
from ultracode.judge import judge_panel
from ultracode.verify import survivors as _survivors, verify_findings


@dataclass
class UltracodeResult:
    task: str
    mode: str  # "solo" | "ultracode"
    answer: str = ""
    decision: Optional[Decision] = None
    plan: Optional[Plan] = None
    findings: List[Finding] = field(default_factory=list)
    survivors: List[Finding] = field(default_factory=list)
    caps_announced: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)

    def __post_init__(self):
        # one guard where ALL answer-producing paths converge (solo, judge fallback,
        # synthesis): a blank answer is a real degradation, never silently confident.
        if not (self.answer or "").strip():
            self.caps_announced.append("WARNING: empty answer produced (all upstream paths degraded)")

    def summary(self) -> dict:
        return {
            "task": self.task[:120],
            "mode": self.mode,
            "n_findings": len(self.findings),
            "n_survivors": len(self.survivors),
            "stages": self.stages,
            "caps": self.caps_announced,
        }


def _finder_prompt(goal: str, context: str, sub_context: str, avoid: List[Finding], directive: str) -> str:
    avoid_block = ""
    if avoid:
        listed = "\n".join(f"- {f.claim} ({f.locator})" for f in avoid[:40])
        avoid_block = f"\nALREADY FOUND (do NOT repeat these; find only NEW, distinct items):\n{listed}\n"
    return (
        f"You are an expert worker. MANDATE: {goal}\n"
        f"{directive}\n"
        f"{('FOCUS: ' + sub_context + chr(10)) if sub_context else ''}"
        f"\nMATERIAL:\n{context}\n"
        f"{avoid_block}\n"
        "Report ONLY concrete, specific, SUPPORTED findings — no speculation, no padding.\n"
        'Reply with ONLY JSON: {"findings":[{"claim":"<specific>","locator":"<file:line, source, or section>",'
        '"evidence":"<the support / mechanism>","severity":"info|low|medium|high|critical"}]}. '
        'Return {"findings":[]} if there is genuinely nothing.'
    )


def _parse_findings(entry: dict, source_label: str) -> List[Finding]:
    if not isinstance(entry, dict) or entry.get("status") != "completed":
        return []
    parsed = extract_json(entry.get("summary") or "")
    items = parsed.get("findings", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
    out: List[Finding] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("claim", "")).strip():
            try:
                out.append(
                    Finding(
                        claim=str(it["claim"]).strip(),
                        locator=str(it.get("locator", "")).strip(),
                        evidence=str(it.get("evidence", "")).strip(),
                        severity=str(it.get("severity", "info")).strip() or "info",
                        source_label=source_label,
                    ).validate()
                )
            except ValueError:
                continue
    return out


def _solo_audit(task: str, context: str, *, model, rt, aux_call_fn):
    """A single thorough pass — the disciplined default the discernment gate
    decides whether to escalate beyond. Returns (findings, answer)."""
    text = aux_call(
        [{"role": "system", "content": "You are an expert auditor. Do a thorough single-pass analysis. "
          "Be specific and locatable; do not pad with speculation."},
         {"role": "user", "content": f"{task}\n\nMATERIAL:\n{context}\n\n"
          'Reply with ONLY JSON: {"findings":[{"claim":"<specific>","locator":"<line/section>",'
          '"evidence":"<why>","severity":"info|low|medium|high|critical"}], "answer":"<lead-first summary>"}'}],
        model=model, temperature=0.3, max_tokens=4000, main_runtime=rt, call_fn=aux_call_fn,
    )
    parsed = extract_json(text)
    items = parsed.get("findings", []) if isinstance(parsed, dict) else []
    findings: List[Finding] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("claim", "")).strip():
            try:
                findings.append(Finding(
                    claim=str(it["claim"]).strip(), locator=str(it.get("locator", "")).strip(),
                    evidence=str(it.get("evidence", "")).strip(),
                    severity=str(it.get("severity", "info")).strip() or "info", source_label="solo",
                ).validate())
            except ValueError:
                continue
    answer = (parsed.get("answer") if isinstance(parsed, dict) else None) or (text if isinstance(text, str) else "")
    return findings, answer


def _solo_summary(findings: List[Finding], answer: str) -> str:
    fs = "\n".join(f"- [{f.severity}] {f.claim} ({f.locator})" for f in findings) or "(no findings)"
    return f"{answer}\n\nFINDINGS ({len(findings)}):\n{fs}"


def run(
    task: str,
    *,
    context: str = "",
    agent: Any = None,
    delegate_fn: Optional[Callable[..., str]] = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    config: Optional[UltracodeConfig] = None,
    model: Optional[str] = None,
    run_id: str = "ultracode",
    force_orchestrate: Optional[bool] = None,
    enable_ledger: bool = True,
    ledger_path: Optional[str] = None,
    kind: str = "auto",
    verify_delegate_fn: Optional[Callable[..., str]] = None,
) -> UltracodeResult:
    # discover cheap, VERIFY STRONG: the hermes verification proved weak skeptics
    # "confirm" false positives. A stronger backend (or execution arbiter) for the
    # skeptics is the precision fix. Defaults to the finder backend if not split.
    verify_delegate_fn = verify_delegate_fn or delegate_fn
    cfg = config or UltracodeConfig()
    led = RunLedger(run_id, path=ledger_path) if enable_ledger else None
    rt = runtime_from_agent(agent)

    decision = decide(task, cfg, force_orchestrate=force_orchestrate)
    tkind = kind if kind != "auto" else classify_kind(task, context)
    if led:
        led.event("decision", {"orchestrate": decision.orchestrate, "shape": decision.shape.value,
                                "reason": decision.reason, "kind": tkind})

    # GENERATIVE tasks use the judge-panel shape (N angles -> score -> graft), not find->verify
    if tkind == TaskKind.GENERATIVE and (decision.orchestrate or force_orchestrate):
        jr = judge_panel(task, context=context, n=cfg.max_finders, delegate_fn=delegate_fn,
                         aux_call_fn=aux_call_fn, config=cfg, agent=agent, model=model)
        res = UltracodeResult(task=task, mode="judge-panel", answer=jr.answer, decision=decision,
                              stages=["judge-panel"],
                              caps_announced=[f"judge-panel: {len(jr.candidates)} candidates from distinct angles; winner={jr.winner_angle}"])
        if led:
            led.event("done", res.summary())
        return res

    # --- restraint: stay solo unless a real signal says otherwise -------------
    if not decision.orchestrate:
        answer = aux_call(
            [
                {"role": "system", "content": "Answer the task directly, concisely, and correctly."},
                {"role": "user", "content": f"{task}\n\n{context}".strip()},
            ],
            model=model, temperature=0.3, max_tokens=2000, main_runtime=rt, call_fn=aux_call_fn,
        )
        res = UltracodeResult(task=task, mode="solo", answer=answer, decision=decision, stages=["solo"])
        if led:
            led.event("done", res.summary())
        return res

    # --- DISCERNMENT: choose DEPTH — solo / light-ensemble / full ------------
    # The recall fix: "not full" still ENSEMBLES (solo union a finder wave) so
    # recall >= any single pass — never the bare-solo single-call variance that
    # dipped recall before. Bare-solo is reserved for trivial turns (handled
    # above). Full adds loop-until-dry. Escalate to full only when triage earns it.
    seed_findings: List[Finding] = []
    pre_stages: List[str] = []
    light = False
    if cfg.discernment and force_orchestrate is not True:
        solo_findings, solo_answer = _solo_audit(task, context, model=model, rt=rt, aux_call_fn=aux_call_fn)
        tv = assess(task, _solo_summary(solo_findings, solo_answer), context_size=len(context),
                    aux_call_fn=aux_call_fn, agent=agent, model=model)
        if led:
            led.event("triage", {"orchestrate": tv.orchestrate, "confidence": tv.confidence,
                                  "stakes": tv.stakes, "gaps": tv.gaps, "reason": tv.reason})
        # STAY SOLO unless an ensemble can be JUSTIFIED. An ensemble only earns its
        # cost when the triage can NAME a concrete gap AND there is MATERIAL to dig
        # into. Two weak-model failure modes this defends against:
        #   - the confidence scalar is unreliable (it hedges even on trivial recall) —
        #     so we gate on the concrete gap-list, not the number;
        #   - on a near-zero-context knowledge question the model hallucinates gaps
        #     ("could add examples"), but finders have NO material to decompose, so a
        #     fan-out is just N redundant re-answers of the same prompt — it cannot
        #     add recall. So a named gap over no material does NOT justify ensembling.
        # Find-all AUDITS (loop_until_dry) and high-stakes work always ensemble.
        no_material = len(context.strip()) < 200
        justified_ensemble = bool(tv.gaps) and not no_material
        if (not decision.loop_until_dry and tv.stakes != "high"
                and not justified_ensemble and solo_answer.strip()):
            res = UltracodeResult(task=task, mode="discerned-solo", answer=solo_answer,
                                  decision=decision, stages=["solo-audit", "triage:solo"],
                                  findings=solo_findings,
                                  caps_announced=[f"discernment: solo suffices (conf={tv.confidence:.2f}, "
                                                  f"stakes={tv.stakes}); ensembling would add cost, not recall"])
            if led:
                led.event("done", res.summary())
            return res
        seed_findings = solo_findings   # always build ON the solo pass (union -> recall)
        # FULL (loop-until-dry) is reserved for genuinely large, unbounded find-all
        # work; everything else that warrants orchestration gets the cheap LIGHT
        # ensemble. This keeps small tasks at ~light cost instead of 80k-token loops.
        go_full = bool(tv.orchestrate and decision.loop_until_dry and len(context) > cfg.full_orchestration_min_chars)
        light = not go_full
        pre_stages = ["solo-audit", "triage:" + ("full" if go_full else "light")]

    # --- AGENT-REASONED APPROACH: the agent decides its OWN method end-to-end --
    # (shape, decomposition, what workers produce, and what VERIFICATION means for
    # this task). The hardcoded kinds.py is only the fallback when the model can't
    # produce a usable plan. This is "figure it out like I do", not a recipe book.
    approach = plan_approach(task, context_size=len(context), max_subtasks=cfg.max_finders,
                             aux_call_fn=aux_call_fn, agent=agent, model=model)
    worker_directive = approach.worker_directive if approach.ok else worker_instruction(tkind)
    skeptic_directive = approach.skeptic_directive if approach.ok else skeptic_instruction(tkind)
    if led:
        led.event("approach", {"ok": approach.ok, "shape": approach.shape, "reasoning": approach.reasoning[:200]})

    # the agent may decide the work is open-ended -> judge-panel
    if approach.ok and approach.shape == "judge_panel":
        jr = judge_panel(task, context=context, n=cfg.max_finders, delegate_fn=delegate_fn,
                         aux_call_fn=aux_call_fn, config=cfg, agent=agent, model=model)
        res = UltracodeResult(task=task, mode="judge-panel", answer=jr.answer, decision=decision,
                              stages=pre_stages + ["approach", "judge-panel"],
                              caps_announced=[f"agent chose judge-panel; winner={jr.winner_angle}"])
        if led:
            led.event("done", res.summary())
        return res

    # --- plan: the agent's own work-list, or the planner as fallback ----------
    if approach.ok and approach.subtasks:
        plan = Plan(subtasks=approach.subtasks, rationale=approach.reasoning, delegated=len(approach.subtasks) > 1)
    else:
        plan = make_plan(task, decision, context="", config=cfg, agent=agent, aux_call_fn=aux_call_fn, model=model)
    caps = list(plan.caps_announced)
    if approach.ok:
        caps.append(f"agent-reasoned approach (shape={approach.shape}): {approach.reasoning[:140]}")
    if seed_findings:
        caps.append(f"discernment: escalated, seeded orchestration with {len(seed_findings)} solo finding(s)")
    if led:
        led.event("plan", {"n_subtasks": len(plan.subtasks), "delegated": plan.delegated, "rationale": plan.rationale})

    # --- find: one finder per subtask, looped-until-dry if the shape says so --
    def finder_round(round_idx: int, known: List[Finding]) -> List[Finding]:
        known = list(seed_findings) + list(known)  # finders always see the solo pass -> find NEW
        if round_idx == 0 or not cfg.reactive_replan:
            subtasks = plan.subtasks
        else:
            # emergent decomposition: re-DERIVE targeted subtasks from findings-so-far,
            # rather than re-running the same finders. The work-list is a living object.
            summaries = [f"{f.claim} ({f.locator})" for f in known]
            subtasks = replan_for_gaps(task, summaries, context=context, max_subtasks=cfg.max_finders,
                                       aux_call_fn=aux_call_fn, agent=agent, model=model)
            if not subtasks:
                return []  # planner declares the surface exhausted -> contributes to dry
        # research depth: when the agent reasoned out its OWN worker_directive, trust it
        # (the plan_approach meta-prompt already teaches depth-per-slice). Only inject the
        # hardcoded per-facet depth mandate as a FALLBACK, when the agent gave us nothing.
        def _directive_for(st_goal: str) -> str:
            if tkind == TaskKind.RESEARCH and not approach.ok:
                return worker_directive + "\n" + research_depth_directive(st_goal)
            return worker_directive
        tasks = [{"goal": _finder_prompt(st.goal, context, st.context, known, _directive_for(st.goal))} for st in subtasks]
        results = delegate_fanout(tasks, parent_agent=agent, max_children=cfg.max_children,
                                  concurrency=cfg.concurrency, delegate_fn=delegate_fn)
        found: List[Finding] = []
        for i, entry in enumerate(results):
            label = subtasks[i % len(subtasks)].goal[:48] if subtasks else f"finder-{i}"
            found.extend(_parse_findings(entry if isinstance(entry, dict) else {}, f"r{round_idx}:{label}"))
        return found

    # loop if the AGENT chose 'loop' (or, in fallback, the heuristic said find-all); light caps it
    want_loop = (approach.shape == "loop") if approach.ok else decision.loop_until_dry
    effective_loop = want_loop and not light
    if effective_loop:
        report = discover(finder_round, config=cfg, seen_keys={f.dedup_key() for f in seed_findings})
        findings = dedupe_findings(seed_findings + report.findings)
        caps.extend(report.caps_announced)
        stages = pre_stages + ["plan", f"discover(loop, {report.rounds_run} rounds, {report.stop_reason})"]
        if led:
            led.event("discovery", {"rounds": report.rounds_run, "fresh_per_round": report.fresh_per_round, "stop": report.stop_reason})
    else:
        # light/non-loop: solo UNION one finder wave -> recall >= any single pass
        findings = dedupe_findings(seed_findings + finder_round(0, []))
        stages = pre_stages + ["plan", "find(light)" if light else "find"]

    # root-cause reconciliation: collapse near-duplicate findings (over-generation)
    if cfg.reconcile:
        before = len(findings)
        findings = reconcile_findings(findings)
        if before != len(findings):
            caps.append(f"reconciled {before} -> {len(findings)} findings (merged near-duplicates)")

    if len(findings) > cfg.max_findings:
        caps.append(f"findings capped at max_findings={cfg.max_findings} (announced)")
        findings = findings[: cfg.max_findings]
    if led:
        led.stage(StageResult(stage="find", findings=findings, caps_announced=caps))

    # --- adversarially verify: independent skeptics, default-to-refuted -------
    if decision.verify and findings:
        verify_findings(findings, context=context, parent_agent=agent, config=cfg, lenses=decision.lenses,
                        delegate_fn=verify_delegate_fn, concurrency=cfg.concurrency, skeptic_directive=skeptic_directive)
        stages.append(f"verify({len(decision.lenses)} lenses, quorum {cfg.effective_quorum(len(decision.lenses))})")
        survs = _survivors(findings)
    else:
        survs = findings
    if led:
        led.stage(StageResult(stage="verify", findings=findings))

    # --- ground-truth ARBITER: execution overrules disputed skeptic votes ----
    # (opt-in; runs model-generated repros). A real bug a weak skeptic wrongly
    # killed gets RESURRECTED when its repro reproduces — the runtime is the
    # impartial arbiter that recovers recall lost to false refutation.
    if cfg.execution_verify and findings and context:
        from ultracode.groundtruth import arbitrate_findings
        arb = arbitrate_findings(findings, context, aux_call_fn=aux_call_fn, agent=agent, model=model)
        survs = _survivors(findings)  # resurrected findings now survive
        stages.append(f"arbiter(execution: {arb['confirmed']} confirmed, {arb['resurrected']} resurrected)")
        if led:
            led.event("arbiter", arb)

    # --- completeness critic (gaps surfaced, never silently dropped) ---------
    crit = completeness_critic(task, findings, caps_announced=caps, agent=agent, aux_call_fn=aux_call_fn, model=model)
    if crit.gaps:
        caps.append(f"completeness critic flagged {len(crit.gaps)} gap(s): {'; '.join(crit.gaps[:3])}")
    elif not crit.independent:
        # empty gaps from a SAME-MODEL critic is UNKNOWN, not verified-complete — say so
        # (don't let absence-of-gaps read as a clean bill of health). Does not gate the loop.
        caps.append("completeness UNKNOWN: same-model critic found no gaps, but shares the finders' blind spots")
    stages.append("critic")
    if led:
        led.event("critic", {"gaps": crit.gaps, "coverage_note": crit.coverage_note,
                             "independent": crit.independent, "raw": (crit.raw or "")[:500]})

    # --- synthesize (solo, non-delegable) -- research: landscape-first to keep depth -
    landscape = tkind == TaskKind.RESEARCH and cfg.research_landscape_synth
    answer = _synthesize(task, survs, findings, crit_note=crit.coverage_note, model=model, rt=rt,
                         aux_call_fn=aux_call_fn, landscape=landscape,
                         synth_directive=(approach.synthesis_directive if approach.ok else ""))
    stages.append("synthesize-landscape" if landscape else "synthesize")

    res = UltracodeResult(
        task=task, mode=("discerned-light" if light else "ultracode"), answer=answer, decision=decision, plan=plan,
        findings=findings, survivors=survs, caps_announced=caps, stages=stages,
    )
    if led:
        led.event("done", res.summary())
    return res


def _synthesize(task, survivors, all_findings, *, crit_note, model, rt, aux_call_fn,
                landscape=False, synth_directive="") -> str:
    refuted = [f for f in all_findings if f not in survivors]
    surv_block = "\n".join(
        f"- [{f.severity}] {f.claim} ({f.locator}) — survived {sum(1 for v in f.votes if v.verdict.value=='confirmed')}/{len(f.votes)} skeptics"
        for f in survivors
    ) or "(no findings survived verification)"
    # research: a refuted claim is UNVERIFIED, not deleted — feed the full union so no
    # discovered sub-point is dropped (verification sorts settled-vs-unverified, it does
    # not filter coverage). code: keep the short load-bearing dissent list.
    refuted_for_synth = refuted if landscape else refuted[:10]
    dissent = "\n".join(f"- {f.claim} ({f.locator})" for f in refuted_for_synth) or "(none)"
    agent_driven = bool(synth_directive.strip())
    if landscape:
        # DEEP RESEARCH: lead-first synthesis is ANTI-depth — it collapses the per-facet
        # investigation the fan-out paid for. When the AGENT reasoned out its own synthesis
        # approach (the meta-prompt teaches it to organize-by-facet/preserve-specifics/hedge-
        # don't-drop), USE IT verbatim. Only fall back to a hardcoded structure if it didn't.
        sys_prompt = "You are the research synthesizer. Preserve every specific; present uncertain material as uncertain, never drop it."
        max_tok = 6000
        if agent_driven:
            instr = ("Write the final research answer following YOUR OWN planned synthesis approach:\n"
                     + synth_directive)
        else:
            instr = (  # fallback only: the agent gave no synthesis_directive
                "Write the final research answer. Organize it BY FACET / claim-axis and COVER EVERY facet "
                "(if one is thin, say so; never drop it). For each: SETTLED facts (with source), CONTESTED "
                "points (Position A vs B, which is better-supported), and UNVERIFIED claims (hedged, not dropped). "
                "PRESERVE every specific verbatim — names, numbers, bounds, mechanisms, example systems. "
                "Lead with STRUCTURE, not a single fact. Do not pad; do not repeat."
            )
    else:
        sys_prompt = "You are the synthesizer. Ranked, lead-first, calibrated, no padding."
        instr = (
            "Write the final answer to the task. Lead with the single most load-bearing result. "
            "Present only verified findings as fact; clearly hedge anything unverified. "
            "If a refuted item is the strongest objection to your conclusion, surface it as a minority report. "
            "Be concrete and ranked; do not pad."
        ) + ("\nADDITIONAL GUIDANCE (supplementary): " + synth_directive if agent_driven else "")
        max_tok = 2500
    dissent_header = (
        "REPORTED BUT UNVERIFIED (a skeptic doubted these — do NOT drop them: place each in the right "
        "facet under UNVERIFIED, stated cautiously; many are true sub-points that simply lacked a citation)"
        if landscape else
        "REFUTED/UNVERIFIED (do not present as fact; mention only if load-bearing)"
    )
    user = (
        f"TASK:\n{task}\n\n"
        f"VERIFIED FINDINGS (survived adversarial verification):\n{surv_block}\n\n"
        f"{dissent_header}:\n{dissent}\n\n"
        f"COMPLETENESS NOTE: {crit_note or '(none)'}\n\n" + instr
    )
    return aux_call(
        [{"role": "system", "content": sys_prompt},
         {"role": "user", "content": user}],
        model=model, temperature=0.3, max_tokens=max_tok, main_runtime=rt, call_fn=aux_call_fn,
    )
