"""Unit tests for the session-level conductor (executive loop)."""

import pytest

from ultracode.conductor import ExecutiveAction, SessionController
from ultracode.config import UltracodeConfig
from ultracode.graph import TaskSpec


def test_ignition_suppresses_conversational():
    sc = SessionController()
    dec = sc.on_user_message("thanks!")
    assert dec.action == ExecutiveAction.SUPPRESS
    assert any("suppressed:trivial" in m for m in sc.log)
    assert sc.intents == []  # no run minted


def test_ignition_scout_first_on_build_turn():
    sc = SessionController()
    dec = sc.on_user_message("find all the security bugs in this service")
    assert dec.action == ExecutiveAction.SCOUT_FIRST
    assert len(sc.intents) == 1


def test_second_message_forks_not_replaces():
    sc = SessionController()
    sc.on_user_message("audit the payment module for vulnerabilities")
    dec = sc.on_user_message("also check the upstream PRs first")
    assert dec.action == ExecutiveAction.RESCOPE
    assert len(sc.intents) == 2  # forked, prior intent preserved
    assert any("goal_revised" in m for m in sc.log)


def test_scout_gate_blocks_blind_expensive_node():
    sc = SessionController()
    # cheap probe with no deps is allowed
    sc.authorize_node(TaskSpec("scout1", kind="scout"))
    # expensive node with no authorizing dep is blocked
    with pytest.raises(ValueError):
        sc.authorize_node(TaskSpec("build1", kind="build"))
    # expensive node WITH a dep is allowed
    sc.authorize_node(TaskSpec("build2", kind="build", deps=("scout1",)))
    assert len(sc.frontier) == 2


def test_fold_constraint_reroutes():
    sc = SessionController()
    sc.fold_constraint("max_concurrent_children", 3, "fork cap")
    sc.fold_constraint("call_llm_threadunsafe", True, "routing globals")
    assert sc.constraints.get("max_concurrent_children") == 3
    assert sc.constraints.get("call_llm_threadunsafe") is True
    assert any("constraint:max_concurrent_children=3" in m for m in sc.log)


def test_budget_governor_fires_and_announces():
    sc = SessionController(UltracodeConfig(run_budget_tokens=1000))
    sc.meters.spend(tokens=1200)
    sigs = sc.run_governors()
    budget = [s for s in sigs if s.action == ExecutiveAction.COLLAPSE]
    assert budget and budget[0].detail["announced"] is True


def test_context_governor_offloads_large_output():
    sc = SessionController()
    sc.on_result("n", output_chars=90_000)
    sigs = sc.run_governors()
    assert any(s.action == ExecutiveAction.OFFLOAD for s in sigs)


def test_no_governor_fires_when_healthy():
    sc = SessionController(UltracodeConfig(run_budget_tokens=10_000))
    sc.on_user_message("audit this for bugs")
    sc.meters.spend(tokens=100)
    assert sc.run_governors() == []


def test_deferred_actions_and_green_commit():
    sc = SessionController()
    sc.defer("add 4-8/4.8 to anthropic thinking substrings if Hermes runs Opus 4.8")
    sc.set_green("a342ec8")
    assert sc.deferred_actions
    assert sc.last_green_commit == "a342ec8"
