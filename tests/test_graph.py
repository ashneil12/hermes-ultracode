"""Unit tests for ultracode.graph — the DAG chassis."""

import pytest

from ultracode.graph import GraphError, TaskGraph, TaskSpec, TaskStatus


def _linear():
    g = TaskGraph()
    g.add(TaskSpec("find"))
    g.add(TaskSpec("verify", deps=("find",)))
    g.add(TaskSpec("synth", deps=("verify",)))
    return g


def test_duplicate_id_rejected():
    g = TaskGraph()
    g.add(TaskSpec("a"))
    with pytest.raises(GraphError):
        g.add(TaskSpec("a"))


def test_unknown_dep_rejected():
    g = TaskGraph()
    g.add(TaskSpec("a", deps=("ghost",)))
    with pytest.raises(GraphError):
        g.validate()


def test_self_dep_rejected():
    g = TaskGraph()
    g.add(TaskSpec("a", deps=("a",)))
    with pytest.raises(GraphError):
        g.validate()


def test_cycle_detected():
    g = TaskGraph()
    g.add(TaskSpec("a", deps=("c",)))
    g.add(TaskSpec("b", deps=("a",)))
    g.add(TaskSpec("c", deps=("b",)))
    with pytest.raises(GraphError):
        g.validate()


def test_ready_queue_progression():
    g = _linear()
    g.validate()
    ready = g.ready()
    assert [r.spec.id for r in ready] == ["find"]
    g.mark_running("find")
    g.mark_done("find", result={"n": 1})
    assert [r.spec.id for r in g.ready()] == ["verify"]
    g.mark_done("verify")
    assert [r.spec.id for r in g.ready()] == ["synth"]
    g.mark_done("synth")
    assert g.is_complete()
    assert g.results()["find"] == {"n": 1}


def test_failure_propagates_as_skip():
    g = _linear()
    g.validate()
    g.mark_done("find")  # find ok
    g.mark_failed("verify", "boom")  # verify fails
    # synth depends on verify -> must become SKIPPED, and graph completes
    g.ready()
    assert g.get("synth").status == TaskStatus.SKIPPED
    assert g.is_complete()
    assert g.summary().get("skipped") == 1
    assert g.summary().get("failed") == 1


def test_parallel_fanout_all_ready_at_once():
    g = TaskGraph()
    g.add(TaskSpec("root"))
    for i in range(5):
        g.add(TaskSpec(f"w{i}", deps=("root",)))
    g.add(TaskSpec("merge", deps=tuple(f"w{i}" for i in range(5))))
    g.validate()
    g.mark_done("root")
    ready_ids = sorted(r.spec.id for r in g.ready())
    assert ready_ids == ["w0", "w1", "w2", "w3", "w4"]  # barrier: merge not ready
    for i in range(5):
        g.mark_done(f"w{i}")
    assert [r.spec.id for r in g.ready()] == ["merge"]


def test_topo_order_stable():
    g = _linear()
    assert g.topo_order() == ["find", "verify", "synth"]
