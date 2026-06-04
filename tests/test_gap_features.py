"""Tests for the upstream-gap-closing features: per-task model pinning, agreement-count,
iterated refutation, resume-from-ledger, the kanban durability bridge, and ultrathink keywords.
All no-network (fakes injected)."""

import json

from ultracode.adapters import delegate_fanout
from ultracode.config import UltracodeConfig
from ultracode.effortkeywords import parse_effort_keywords, resolve
from ultracode.schema import Finding, SubtaskSpec, dedupe_findings, reconcile_findings
from ultracode.verify import verify_to_convergence, survivors


# ---- per-task / per-worker model pinning ----

def test_subtaskspec_emits_model():
    t = SubtaskSpec(goal="x", model="cheap-mini").validate().to_delegate_task()
    assert t["model"] == "cheap-mini"
    assert "model" not in SubtaskSpec(goal="x").to_delegate_task()  # absent by default


def test_delegate_fanout_injects_worker_model_without_clobbering():
    seen = []

    def fake(*, tasks, parent_agent, role):
        seen.extend(tasks)
        return json.dumps({"results": [{"task_index": i, "status": "completed", "summary": "ok"}
                                       for i in range(len(tasks))]})

    tasks = [{"goal": "a"}, {"goal": "b", "model": "explicit"}]
    delegate_fanout(tasks, delegate_fn=fake, max_children=2, worker_model="worker-mini")
    by_goal = {t["goal"]: t.get("model") for t in seen}
    assert by_goal["a"] == "worker-mini"   # injected where absent
    assert by_goal["b"] == "explicit"      # a task's own model is never overridden


def test_delegate_fanout_raise_on_error():
    def bad(*, tasks, parent_agent, role):
        return json.dumps({"error": "boom"})

    # default: degrade, no raise
    out = delegate_fanout([{"goal": "x"}], delegate_fn=bad)
    assert out[0]["status"] == "error"
    # raise_on_error=True surfaces it
    try:
        delegate_fanout([{"goal": "x"}], delegate_fn=bad, raise_on_error=True)
        assert False, "should have raised"
    except RuntimeError as e:
        assert "errored" in str(e)


# ---- agreement-count on dedup/reconcile ----

def test_dedupe_counts_agreement_instead_of_dropping():
    fs = [Finding(claim="bug in auth", locator="a.py:10"),
          Finding(claim="bug in auth", locator="a.py:10"),
          Finding(claim="bug in auth", locator="a.py:10")]
    out = dedupe_findings(fs)
    assert len(out) == 1
    assert out[0].agreement_count == 3   # 3 independent finders converged, counted not dropped


def test_reconcile_accumulates_agreement():
    fs = [Finding(claim="SQL injection in login handler", locator="login.py:5", agreement_count=2),
          Finding(claim="SQL injection at the login handler", locator="login.py:5")]
    out = reconcile_findings(fs)
    assert len(out) == 1
    assert out[0].agreement_count == 3   # 2 + 1 merged


def test_agreement_count_survives_roundtrip():
    f = Finding(claim="x", locator="a:1", agreement_count=4)
    assert Finding.from_dict(f.as_dict()).agreement_count == 4


# ---- iterated refutation to convergence ----

def test_verify_to_convergence_rechallenges_survivors():
    # a finding that survives round 1 but is refuted in a later independent pass must be dropped.
    rounds_seen = []

    def fake_verify(findings, **kw):
        n = len(rounds_seen)
        rounds_seen.append([f.claim for f in findings])
        for f in findings:
            # claim "flaky" survives round 1, dies round 2; "solid" always survives
            f.survived = not (f.claim == "flaky" and n >= 1)
        return findings

    import ultracode.verify as V
    orig = V.verify_findings
    V.verify_findings = fake_verify
    try:
        fs = [Finding(claim="solid", locator="a:1"), Finding(claim="flaky", locator="b:2")]
        verify_to_convergence(fs, rounds=3)
        alive = [f.claim for f in survivors(fs)]
        assert alive == ["solid"]          # flaky refuted on re-challenge
        assert len(rounds_seen) >= 2        # it actually iterated
    finally:
        V.verify_findings = orig


def test_verify_to_convergence_single_round_is_one_pass():
    calls = {"n": 0}

    def fake_verify(findings, **kw):
        calls["n"] += 1
        for f in findings:
            f.survived = True
        return findings

    import ultracode.verify as V
    orig = V.verify_findings
    V.verify_findings = fake_verify
    try:
        verify_to_convergence([Finding(claim="x", locator="a:1")], rounds=1)
        assert calls["n"] == 1   # rounds=1 -> exactly one pass (backward compatible)
    finally:
        V.verify_findings = orig


# ---- resume-from-ledger ----

def test_resume_state_rebuilds_findings_and_seen_keys(tmp_path):
    from ultracode.ledger import RunLedger
    led = RunLedger("run42", path=tmp_path / "run42.jsonl")
    led.finding(Finding(claim="found A", locator="a.py:1"))
    led.finding(Finding(claim="found B", locator="b.py:2"))
    led.finding(Finding(claim="found A", locator="a.py:1"))  # dup recorded

    state = RunLedger("run42", path=tmp_path / "run42.jsonl").resume_state()
    assert state["resumed"] is True
    assert len(state["findings"]) == 2          # deduped
    assert len(state["seen_keys"]) == 2         # ready to prime a loop-until-dry seen-set


def test_resume_state_empty_for_fresh_run(tmp_path):
    from ultracode.ledger import RunLedger
    state = RunLedger("nope", path=tmp_path / "nope.jsonl").resume_state()
    assert state["resumed"] is False and state["findings"] == [] and state["seen_keys"] == set()


# ---- ultrathink keywords ----

def test_parse_effort_keywords_strips_and_resolves_highest():
    cleaned, eff = parse_effort_keywords("ok ultrathink and also think harder about this")
    assert eff == "xhigh"                  # highest among the two wins
    assert "ultrathink" not in cleaned and "think harder" not in cleaned
    assert cleaned == "ok and also about this"


def test_parse_effort_keywords_none_when_absent():
    assert parse_effort_keywords("just a normal message") == ("just a normal message", None)


def test_resolve_is_upward_only():
    # below session effort -> ignored
    assert resolve("think harder", "xhigh") == ("", "xhigh", False)
    # above session effort -> bump
    cleaned, eff, bumped = resolve("ultrathink the thing", "medium")
    assert eff == "xhigh" and bumped is True and cleaned == "the thing"


# ---- kanban durability bridge (injected fakes; no host) ----

def test_persist_as_swarm_maps_subtasks_with_injected_fake():
    from ultracode.durable import persist_as_swarm

    class FakeSpec:  # mirrors the REAL SwarmWorkerSpec(profile, title, body)
        def __init__(self, profile, title, body):
            self.profile, self.title, self.body = profile, title, body

    captured = {}

    def fake_create(conn, *, goal, workers, verifier_assignee, synthesizer_assignee,
                    verifier_title, synthesizer_title, created_by):
        captured.update(goal=goal, n_workers=len(workers), v_assignee=verifier_assignee,
                        profiles=[w.profile for w in workers])

        class Created:
            def as_dict(self):
                return {"root_id": "root-1", "worker_ids": ["w0", "w1"],
                        "verifier_id": "v0", "synthesizer_id": "s0"}
        return Created()

    subs = [SubtaskSpec(goal="audit file A", label="A"), SubtaskSpec(goal="audit file B", label="B")]
    handle = persist_as_swarm("audit the repo", subs, conn=object(),
                              verifier_assignee="reviewer", synthesizer_assignee="writer",
                              worker_profile="auditor", create_fn=fake_create, spec_cls=FakeSpec)
    assert handle.root_id == "root-1"
    assert handle.worker_ids == ["w0", "w1"]
    assert handle.verifier_id == "v0" and handle.synthesizer_id == "s0"
    assert captured["goal"] == "audit the repo" and captured["n_workers"] == 2
    assert captured["v_assignee"] == "reviewer" and captured["profiles"] == ["auditor", "auditor"]


def test_persist_as_swarm_rejects_empty_subtasks():
    from ultracode.durable import persist_as_swarm
    try:
        persist_as_swarm("goal", [], verifier_assignee="v", synthesizer_assignee="s",
                         create_fn=lambda *a, **k: None, spec_cls=object)
        assert False, "should reject empty subtasks"
    except ValueError as e:
        assert "at least one" in str(e)


# ---- regressions for the bugs the adversarial review found ----

def test_resume_does_not_double_count_agreement(tmp_path):
    # the live bug: harness records a finding in BOTH 'find' and 'verify' stages; resume must NOT
    # re-sum the already-accumulated agreement_count (idempotent dedup-by-max, not dedupe's sum).
    from ultracode.ledger import RunLedger
    from ultracode.schema import StageResult
    p = tmp_path / "r.jsonl"
    led = RunLedger("r", path=p)
    f = Finding(claim="dup finding", locator="x.py:1", agreement_count=3)
    led.stage(StageResult(stage="find", findings=[f]))
    led.stage(StageResult(stage="verify", findings=[f]))   # same finding, recorded again
    state = RunLedger("r", path=p).resume_state()
    assert len(state["findings"]) == 1
    assert state["findings"][0].agreement_count == 3        # NOT 6
    # idempotent across repeated resumes
    assert RunLedger("r", path=p).resume_state()["findings"][0].agreement_count == 3


def test_resume_survives_partial_records(tmp_path):
    # a missing-payload or missing-claim record must be SKIPPED, not crash the resume
    p = tmp_path / "bad.jsonl"
    p.write_text(
        '{"seq":0,"kind":"finding"}\n'                                    # no payload
        '{"seq":1,"kind":"finding","payload":{"locator":"x:1"}}\n'        # no claim
        '{"seq":2,"kind":"cap_announced"}\n'                              # no payload
        '{"seq":3,"kind":"finding","payload":{"claim":"good","locator":"y:2"}}\n')  # valid
    from ultracode.ledger import RunLedger
    state = RunLedger("bad", path=p).resume_state()           # must not raise
    assert [f.claim for f in state["findings"]] == ["good"]   # only the valid one survives


def test_finding_agreement_count_zero_roundtrips():
    f = Finding(claim="x", locator="a:1", agreement_count=0)
    assert Finding.from_dict(f.as_dict()).agreement_count == 0   # 0 not clobbered to 1


def test_worker_model_preserves_explicit_falsy_model():
    seen = []

    def fake(*, tasks, parent_agent, role):
        seen.extend(tasks)
        return json.dumps({"results": [{"task_index": i, "status": "completed", "summary": "ok"}
                                       for i in range(len(tasks))]})

    # an explicit model key (even None, meaning "backend default") must NOT be overridden
    delegate_fanout([{"goal": "a", "model": None}], delegate_fn=fake, worker_model="mini")
    assert "model" in seen[0] and seen[0]["model"] is None


def test_ultrathink_phrase_tolerates_irregular_whitespace():
    cleaned, eff = parse_effort_keywords("please think   harder here")  # multiple spaces
    assert eff == "high" and "harder" not in cleaned


def test_resolve_bumps_when_session_effort_unrecognized():
    # an unrankable session effort can't block the bump (ultracode bias: up)
    cleaned, eff, bumped = resolve("ultrathink it", "potato")
    assert eff == "xhigh" and bumped is True


def test_ultrathink_no_false_match_on_substrings():
    # "rethink"/"ultrathinking" must not trigger (whole-word)
    assert parse_effort_keywords("let me rethink and keep ultrathinking") == \
        ("let me rethink and keep ultrathinking", None)
