"""Tests for the cognitive core: verify, discovery, steering, planner, and the
full harness.run() — all driven by injected fakes (no live model)."""

import json

from ultracode.config import UltracodeConfig
from ultracode.discovery import discover
from ultracode.harness import run
from ultracode.planner import plan as make_plan
from ultracode.schema import Finding, OrchestrationShape, Verdict, VerifyLens
from ultracode.steering import decide
from ultracode.verify import survivors, verify_findings


# ----------------------------- fakes ---------------------------------------

def _delegate_skeptics(verdict_for):
    """Fake delegate_fn for verifier fan-out: verdict_for(claim) -> 'confirmed'|'refuted'."""
    def fn(*, tasks, parent_agent, role):
        results = []
        for i, t in enumerate(tasks):
            goal = t["goal"]
            # the claim is embedded after 'CLAIM: '
            claim = goal.split("CLAIM:", 1)[1].split("\n", 1)[0].strip() if "CLAIM:" in goal else ""
            v = verdict_for(claim)
            body = json.dumps({"verdict": v, "rationale": "because mechanism X"})
            results.append({"task_index": i, "status": "completed", "summary": body})
        return json.dumps({"results": results})
    return fn


# ----------------------------- verify --------------------------------------

def test_verify_survival_by_quorum():
    findings = [Finding(claim="real bug", locator="a:1"), Finding(claim="false alarm", locator="b:2")]
    fn = _delegate_skeptics(lambda c: "confirmed" if "real" in c else "refuted")
    verify_findings(findings, config=UltracodeConfig(), delegate_fn=fn)
    real = next(f for f in findings if "real" in f.claim)
    false = next(f for f in findings if "false" in f.claim)
    assert real.survived is True and real.verdict == Verdict.CONFIRMED
    assert false.survived is False and false.verdict == Verdict.REFUTED
    assert [f.claim for f in survivors(findings)] == ["real bug"]


def test_verify_noncompletion_abstains_not_kills():
    # defend mode: a finding carries its own evidence; a skeptic that doesn't
    # complete ABSTAINS (UNKNOWN) and must NOT silently kill a real finding.
    findings = [Finding(claim="x", locator="a:1")]

    def fn(*, tasks, parent_agent, role):
        return json.dumps({"results": [{"task_index": i, "status": "timeout", "summary": None} for i in range(len(tasks))]})

    verify_findings(findings, config=UltracodeConfig(), delegate_fn=fn)
    assert findings[0].survived is True            # UNKNOWN does not kill
    assert findings[0].verdict == Verdict.PARTIAL  # but it stays unverified
    assert all(v.verdict == Verdict.PARTIAL for v in findings[0].votes)


def test_verify_no_mechanism_does_not_confirm():
    # a 'confirmed' with no mechanism abstains — neither confirms nor kills.
    findings = [Finding(claim="x", locator="a:1")]

    def fn(*, tasks, parent_agent, role):
        return json.dumps({"results": [{"task_index": i, "status": "completed",
                                        "summary": json.dumps({"verdict": "confirmed", "rationale": ""})} for i in range(len(tasks))]})

    verify_findings(findings, config=UltracodeConfig(), delegate_fn=fn)
    assert findings[0].survived is True            # not killed
    assert findings[0].verdict == Verdict.PARTIAL  # but NOT confirmed (no mechanism)


def test_verify_prove_mode_for_claims():
    # prove mode: a bare claim survives ONLY if a quorum confirms it with mechanism.
    true_claim = Finding(claim="this is a real true claim")
    false_claim = Finding(claim="this is a false claim")

    def fn(*, tasks, parent_agent, role):
        results = []
        for i, t in enumerate(tasks):
            claim = t["goal"].split("CLAIM:", 1)[1].split("\n", 1)[0].strip()
            v = "confirmed" if "true" in claim else "refuted"
            results.append({"task_index": i, "status": "completed",
                            "summary": json.dumps({"verdict": v, "rationale": "mechanism"})})
        return json.dumps({"results": results})

    verify_findings([true_claim, false_claim], config=UltracodeConfig(), delegate_fn=fn, survival_mode="prove")
    assert true_claim.survived is True
    assert false_claim.survived is False


# ----------------------------- discovery -----------------------------------

def test_discovery_loops_until_dry_and_dedups():
    rounds = [
        [Finding(claim="a", locator="x:1"), Finding(claim="b", locator="x:2")],
        [Finding(claim="a", locator="x:1"), Finding(claim="c", locator="x:3")],  # 'a' is dup
        [],  # dry 1
        [],  # dry 2 -> stop
    ]

    def round_fn(i, known):
        return rounds[i] if i < len(rounds) else []

    rep = discover(round_fn, config=UltracodeConfig(discovery_dry_rounds=2, discovery_max_rounds=10))
    claims = sorted(f.claim for f in rep.findings)
    assert claims == ["a", "b", "c"]  # deduped
    assert rep.fresh_per_round[:4] == [2, 1, 0, 0]
    assert "dry" in rep.stop_reason


# ----------------------------- steering ------------------------------------

def test_steering_stays_solo_on_trivial():
    d = decide("thanks!", UltracodeConfig())
    assert d.orchestrate is False
    assert d.shape == OrchestrationShape.SOLO


def test_steering_orchestrates_find_all():
    d = decide("find all the bugs in this module", UltracodeConfig())
    assert d.orchestrate is True
    assert d.shape == OrchestrationShape.LOOP_UNTIL_DRY
    assert d.loop_until_dry is True


def test_steering_force_override():
    d = decide("say hello", UltracodeConfig(), force_orchestrate=True)
    assert d.orchestrate is True


# ----------------------------- planner -------------------------------------

def test_planner_parses_and_caps():
    def aux(**kwargs):
        return json.dumps({"rationale": "by hypothesis", "subtasks": [{"goal": f"h{i}", "context": ""} for i in range(10)]})

    d = decide("debug why the test fails", UltracodeConfig(max_finders=4))
    p = make_plan("debug why the test fails", d, config=UltracodeConfig(max_finders=4), aux_call_fn=aux)
    assert len(p.subtasks) == 4  # capped
    assert any("capped" in c for c in p.caps_announced)
    assert p.delegated is True


def test_planner_scaledown_single_subtask():
    def aux(**kwargs):
        return json.dumps({"rationale": "trivial", "subtasks": [{"goal": "just do it"}]})

    d = decide("review this", UltracodeConfig())
    p = make_plan("review this", d, aux_call_fn=aux)
    assert len(p.subtasks) == 1
    assert p.delegated is False  # scale-down gate fired


# ----------------------------- harness end-to-end --------------------------

def _make_harness_fakes(triage_orchestrate=True):
    """aux_call_fn handles solo-audit/triage/plan/critic/synth; delegate_fn handles finders+skeptics."""
    def aux(**kwargs):
        sys = kwargs["messages"][0]["content"].lower()
        if "expert auditor" in sys:  # solo audit
            return json.dumps({"findings": [{"claim": "off-by-one maybe", "locator": "loop.py:9",
                                             "evidence": "weak", "severity": "low"}],
                               "answer": "solo: a possible off-by-one"})
        if "deciding whether to escalate" in sys:  # triage / discernment
            return json.dumps({"confidence": 0.5 if triage_orchestrate else 0.95,
                               "stakes": "high" if triage_orchestrate else "low",
                               "gaps": ["security unchecked"] if triage_orchestrate else [],
                               "orchestrate": triage_orchestrate, "reason": "test"})
        if "planner" in sys:
            return json.dumps({"rationale": "by lens", "subtasks": [{"goal": "hunt logic bugs"}, {"goal": "hunt security bugs"}]})
        if "completeness critic" in sys:
            return json.dumps({"gaps": [], "coverage_note": "looks covered"})
        if "synthesizer" in sys:
            return "FINAL: the SQL injection is the load-bearing issue."
        return "solo answer"

    def delegate(*, tasks, parent_agent, role):
        results = []
        for i, t in enumerate(tasks):
            goal = t["goal"]
            if "adversarial verifier" in goal:  # skeptic
                claim = goal.split("CLAIM:", 1)[1].split("\n", 1)[0].strip()
                v = "confirmed" if "sql" in claim.lower() else "refuted"
                results.append({"task_index": i, "status": "completed",
                                "summary": json.dumps({"verdict": v, "rationale": "mech"})})
            else:  # finder
                if "security" in goal.lower():
                    body = {"findings": [{"claim": "SQL injection in query builder", "locator": "db.py:42", "evidence": "unsanitized", "severity": "critical"}]}
                else:
                    body = {"findings": [{"claim": "off-by-one maybe", "locator": "loop.py:9", "evidence": "weak", "severity": "low"}]}
                results.append({"task_index": i, "status": "completed", "summary": json.dumps(body)})
        return json.dumps({"results": results})

    return aux, delegate


def test_harness_end_to_end_ultracode():
    aux, delegate = _make_harness_fakes()
    res = run(
        "find all security and logic bugs in this code",
        context="<code here>",
        aux_call_fn=aux, delegate_fn=delegate, force_orchestrate=True,  # exercise the FULL pipeline
        config=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES]),
        enable_ledger=False,
    )
    assert res.mode == "ultracode"
    assert len(res.findings) >= 2
    # the SQL injection survives skeptics; the weak off-by-one is refuted
    surv_claims = [f.claim for f in res.survivors]
    assert any("SQL" in c for c in surv_claims)
    assert not any("off-by-one" in c for c in surv_claims)
    assert "synthesize" in res.stages
    assert "SQL injection" in res.answer


def test_harness_solo_path():
    aux, delegate = _make_harness_fakes()
    res = run("hi there", aux_call_fn=aux, delegate_fn=delegate, enable_ledger=False)
    assert res.mode == "solo"
    assert res.answer == "solo answer"


def test_harness_discernment_light_ensembles_for_recall():
    # triage says "not full" -> LIGHT ensemble (solo UNION one finder wave, no loop),
    # so recall >= a single pass. NOT bare-solo, NOT the full loop.
    aux, delegate = _make_harness_fakes(triage_orchestrate=False)
    res = run("find all security and logic bugs in this code", context="<code>",
              aux_call_fn=aux, delegate_fn=delegate, enable_ledger=False,
              config=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES]))
    assert res.mode == "discerned-light"
    assert res.stages[:2] == ["solo-audit", "triage:light"]
    assert "find(light)" in res.stages and "synthesize" in res.stages
    assert not any("discover(loop" in s for s in res.stages)  # no expensive loop
    # union of solo + finders, verified: the planted SQLi survives
    assert any("SQL" in f.claim for f in res.survivors)


def test_harness_discernment_full_only_on_large_findall():
    # triage escalates AND it's a large find-all -> FULL (loop). Small inputs stay light.
    aux, delegate = _make_harness_fakes(triage_orchestrate=True)
    big = "def f():\n    return 1\n" * 400  # > full_orchestration_min_chars
    res = run("find all security and logic bugs in this code", context=big,
              aux_call_fn=aux, delegate_fn=delegate, enable_ledger=False,
              config=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES]))
    assert res.mode == "ultracode"
    assert res.stages[:2] == ["solo-audit", "triage:full"]
    assert any("SQL" in f.claim for f in res.survivors)


def test_harness_discernment_small_findall_stays_light():
    # even when triage wants orchestration, a SMALL find-all stays light (cheap)
    aux, delegate = _make_harness_fakes(triage_orchestrate=True)
    res = run("find all security and logic bugs in this code", context="<short code>",
              aux_call_fn=aux, delegate_fn=delegate, enable_ledger=False,
              config=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES]))
    assert res.mode == "discerned-light"
    assert not any("discover(loop" in s for s in res.stages)


def test_streaming_discovery_spawns_followup_finder_on_the_fly():
    # the no-barrier path: a seed finder returns a HIGH-severity finding, which spawns a
    # targeted follow-up finder ON THE FLY (via pipeline.run_reactive) — not a next round.
    def aux(**kwargs):
        sysm = kwargs["messages"][0]["content"].lower()
        if "expert auditor" in sysm:
            return json.dumps({"findings": [], "answer": "solo: nothing"})
        if "ultracode orchestrator" in sysm:   # agent reasons a LOOP with one seed finder
            return json.dumps({"reasoning": "probe the auth surface deeply", "shape": "loop",
                               "worker_directive": "find bugs", "skeptic_directive": "verify",
                               "synthesis_directive": "combine", "subtasks": [{"goal": "probe auth"}]})
        if "re-planning" in sysm:               # react() -> spawn a follow-up from the hot finding
            return json.dumps({"subtasks": [{"goal": "deep dive the token check"}]})
        if "completeness critic" in sysm:
            return json.dumps({"gaps": [], "coverage_note": "ok"})
        if "synthesizer" in sysm:
            return "FINAL."
        return "answer"

    def delegate(*, tasks, parent_agent, role):
        out = []
        for i, t in enumerate(tasks):
            goal = t["goal"]
            if "adversarial verifier" in goal:
                out.append({"task_index": i, "status": "completed", "summary": json.dumps({"verdict": "confirmed", "rationale": "m"})})
            elif "deep dive" in goal:            # the SPAWNED follow-up: returns a low finding (no further spawn)
                out.append({"task_index": i, "status": "completed",
                            "summary": json.dumps({"findings": [{"claim": "minor token nit", "locator": "t.py:9", "evidence": "e", "severity": "low"}]})})
            else:                                 # the seed finder: returns a HIGH finding -> triggers a spawn
                out.append({"task_index": i, "status": "completed",
                            "summary": json.dumps({"findings": [{"claim": "auth bypass", "locator": "auth.py:3", "evidence": "e", "severity": "high"}]})})
        return json.dumps({"results": out})

    # AUTO default: streaming_discovery=None + a concurrency-safe backend (concurrency=4)
    # -> streaming engages automatically, no explicit flag needed.
    res = run("audit the auth code thoroughly", context="x" * 200,
              aux_call_fn=aux, delegate_fn=delegate, force_orchestrate=True, enable_ledger=False,
              config=UltracodeConfig(concurrency=4, verify_lenses=[VerifyLens.CORRECTNESS]))
    assert any("stream-discover" in s for s in res.stages)               # the streaming path ran
    assert any("spawned" in c and "ON THE FLY" in c for c in res.caps_announced)  # announced
    claims = {f.claim for f in res.findings}
    assert "auth bypass" in claims and "minor token nit" in claims        # seed + the on-the-fly spawn both ran


def test_agent_reasoned_loop_wins_over_keyword_heuristic():
    # the HIGH fix: when the AGENT reasons shape='loop', the full loop must run on a big,
    # orchestration-worthy task even when the keyword steerer saw no 'find-all' phrasing
    # (no silent demotion of the reasoned shape to a single light wave).
    big = "def f():\n    return 1\n" * 400  # > full_orchestration_min_chars, no find-all words

    def aux(**kwargs):
        sysm = kwargs["messages"][0]["content"].lower()
        if "expert auditor" in sysm:
            return json.dumps({"findings": [], "answer": "solo: nothing obvious"})
        if "deciding whether to escalate" in sysm:
            return json.dumps({"confidence": 0.4, "stakes": "high", "gaps": ["depth"], "orchestrate": True})
        if "ultracode orchestrator" in sysm:  # plan_approach -> agent reasons a LOOP
            return json.dumps({"reasoning": "open-ended; sweep until dry", "shape": "loop",
                               "worker_directive": "find issues", "skeptic_directive": "verify",
                               "synthesis_directive": "combine", "subtasks": [{"goal": "probe area A"}]})
        if "re-planning" in sysm:   # signal the surface is exhausted -> loop terminates
            return json.dumps({"subtasks": []})
        if "completeness critic" in sysm:
            return json.dumps({"gaps": [], "coverage_note": "ok"})
        if "synthesizer" in sysm:
            return "FINAL."
        return "answer"

    def delegate(*, tasks, parent_agent, role):
        out = []
        for i, t in enumerate(tasks):
            if "adversarial verifier" in t["goal"]:
                out.append({"task_index": i, "status": "completed", "summary": json.dumps({"verdict": "confirmed", "rationale": "m"})})
            else:
                out.append({"task_index": i, "status": "completed",
                            "summary": json.dumps({"findings": [{"claim": "issue in A", "locator": "a.py:3", "evidence": "e", "severity": "medium"}]})})
        return json.dumps({"results": out})

    res = run("Investigate and explain the retry/backoff behavior in depth", context=big,
              aux_call_fn=aux, delegate_fn=delegate, enable_ledger=False,
              config=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS]))
    assert res.mode == "ultracode"                                   # looped, not demoted to light
    assert any("discover(loop" in s for s in res.stages)             # the loop actually ran


def test_cost_capped_loop_is_announced_not_silent():
    # when the size/stakes gate caps an intended loop to one wave, it must be ANNOUNCED.
    aux, delegate = _make_harness_fakes(triage_orchestrate=True)
    # small context + a find-all task: heuristic wants loop, but it's under the size gate
    res = run("find all bugs", context="<short>", aux_call_fn=aux, delegate_fn=delegate,
              enable_ledger=False, config=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS]))
    assert res.mode == "discerned-light"
    assert any("capped to a single light wave" in c for c in res.caps_announced)  # not silent


def test_harness_discernment_stays_solo_when_bounded_and_confident():
    # the cost fix for general-use: a BOUNDED task (not find-all) where triage is
    # confident (high conf, low stakes, no gaps) terminates at solo — ensembling a
    # closed-form, already-saturated answer only multiplies cost for zero recall.
    aux, delegate = _make_harness_fakes(triage_orchestrate=False)
    res = run("investigate and explain how the retry backoff works", context="<notes>",
              aux_call_fn=aux, delegate_fn=delegate, enable_ledger=False,
              config=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS]))
    assert res.mode == "discerned-solo"           # NOT discerned-light
    assert res.stages == ["solo-audit", "triage:solo"]
    assert not any("find(" in s for s in res.stages)   # no finder wave was spawned


def test_replan_for_gaps_returns_new_targeted_subtasks():
    from ultracode.planner import replan_for_gaps

    def aux(**kwargs):
        # only fire on the RE-PLANNING system prompt
        assert "re-planning" in kwargs["messages"][0]["content"].lower()
        return json.dumps({"subtasks": [{"goal": "check auth bypass"}, {"goal": "check race conditions"}]})

    subs = replan_for_gaps("audit this service", ["found sqli (db:1)"], context="<code>", aux_call_fn=aux)
    assert [s.goal for s in subs] == ["check auth bypass", "check race conditions"]


def test_replan_empty_signals_dry():
    from ultracode.planner import replan_for_gaps
    assert replan_for_gaps("x", [], aux_call_fn=lambda **k: json.dumps({"subtasks": []})) == []


def test_plan_approach_agent_decides_its_own_method():
    from ultracode.planner import plan_approach

    def aux(**kwargs):
        assert "ultracode orchestrator" in kwargs["messages"][0]["content"].lower()
        return json.dumps({"reasoning": "research task; decompose by protocol generation",
                           "shape": "parallel", "worker_directive": "report only sourced factual claims",
                           "skeptic_directive": "check the cited source actually supports the claim",
                           "synthesis_directive": "lead with the key difference",
                           "subtasks": [{"goal": "HTTP/2 changes"}, {"goal": "HTTP/3 changes"}]})

    a = plan_approach("compare HTTP versions", aux_call_fn=aux)
    assert a.ok and a.shape == "parallel" and len(a.subtasks) == 2
    assert "sourced" in a.worker_directive          # the agent decided what workers produce
    assert "source" in a.skeptic_directive           # the agent decided what verification MEANS


def test_plan_approach_falls_back_when_model_cant_plan():
    from ultracode.planner import plan_approach
    a = plan_approach("x", aux_call_fn=lambda **k: "not json at all")
    assert a.ok is False  # harness then uses the kinds.py heuristic default


def _confirm_all(*, tasks, parent_agent, role):
    return json.dumps({"results": [{"task_index": i, "status": "completed",
                                    "summary": json.dumps({"verdict": "confirmed", "rationale": "m"})} for i in range(len(tasks))]})


def test_voi_severity_weighted_lens_count():
    # VOI: critical gets all 3 lenses, low gets 1 — fewer skeptic calls where cheap.
    crit = Finding(claim="rce", locator="a:1", severity="critical")
    med = Finding(claim="leak", locator="b:2", severity="medium")
    low = Finding(claim="nit", locator="c:3", severity="low")
    calls = {"n": 0}

    def fn(*, tasks, parent_agent, role):
        calls["n"] += len(tasks)
        return _confirm_all(tasks=tasks, parent_agent=parent_agent, role=role)

    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES])
    verify_findings([crit, med, low], config=cfg, delegate_fn=fn)
    # critical/high keep all lenses; non-critical get 2 (never 1 — a kill needs a quorum of 2)
    assert len(crit.votes) == 3 and len(med.votes) == 2 and len(low.votes) == 2
    assert calls["n"] == 7  # 3+2+2, not 9 — saves a lens on the non-critical without 1-lens fragility
    assert all(f.survived for f in (crit, med, low))  # all confirmed -> all survive


def test_voi_low_severity_cannot_be_killed_by_a_single_skeptic():
    # the large-dense regression: one over-zealous skeptic must NOT kill a real
    # low-severity finding. With 2 lenses, a single refute is insufficient.
    low = Finding(claim="minor issue", locator="x:1", severity="low")

    def one_refute(*, tasks, parent_agent, role):
        # first lens refutes, second confirms -> 1 kill, not a quorum
        out = []
        for i in range(len(tasks)):
            v = "refuted" if i == 0 else "confirmed"
            out.append({"task_index": i, "status": "completed", "summary": json.dumps({"verdict": v, "rationale": "m"})})
        return json.dumps({"results": out})

    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES])
    verify_findings([low], config=cfg, delegate_fn=one_refute)
    assert low.survived is True  # 1 refute < quorum 2 -> not killed


def test_voi_off_uses_all_lenses_uniformly():
    low = Finding(claim="nit", locator="c:3", severity="low")
    cfg = UltracodeConfig(voi_verify=False, verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES])
    verify_findings([low], config=cfg, delegate_fn=_confirm_all)
    assert len(low.votes) == 3
