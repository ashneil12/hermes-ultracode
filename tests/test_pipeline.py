"""Tests for the reactive / no-barrier orchestration driver (no live model)."""

import threading

from ultracode.graph import TaskGraph, TaskSpec
from ultracode.pipeline import drive_graph, run_reactive


def _key(s):
    return s["id"]


def test_reactive_spawns_a_followup_on_the_fly():
    # the core capability: a worker's RESULT spawns a new worker that then runs.
    def execute(spec):
        return {"id": spec["id"], "open_thread": spec["id"] == "seed"}

    def react(result, spec, results):
        if result.get("open_thread"):
            return [{"id": "followup"}]          # spawned because of what 'seed' found
        return []

    rep = run_reactive([{"id": "seed"}], execute, react, concurrency=4, spec_key=_key)
    ran = {r["id"] for r in rep.results}
    assert "seed" in ran and "followup" in ran    # the on-the-fly spawn actually executed
    assert rep.spawned == 1 and rep.dispatched == 2


def test_reactive_spawn_runs_WHILE_others_still_in_flight():
    # DETERMINISTIC proof of no-barrier: the fast worker returns and spawns a follow-up,
    # and that follow-up runs to completion WHILE the slow worker is still blocked. If the
    # scheduler waited for the whole batch (a barrier), the slow worker would block forever
    # waiting on the spawn -> deadlock; this passing IS the proof the spawn overlapped.
    spawned_done = threading.Event()
    order = []
    lock = threading.Lock()

    def execute(spec):
        k = spec["id"]
        if k == "slow":
            assert spawned_done.wait(timeout=3), "spawn never ran while slow was in flight (barrier!)"
            with lock:
                order.append("slow")
            return {"id": k}
        if k == "fast":
            with lock:
                order.append("fast")
            return {"id": k, "spawn": True}
        if k == "spawned":
            with lock:
                order.append("spawned")
            spawned_done.set()
            return {"id": k}
        return {"id": k}

    def react(result, spec, results):
        return [{"id": "spawned"}] if result.get("spawn") else []

    rep = run_reactive([{"id": "slow"}, {"id": "fast"}], execute, react, concurrency=4, spec_key=_key)
    assert spawned_done.is_set()
    assert order.index("spawned") < order.index("slow")   # spawn finished BEFORE slow did
    assert rep.peak_in_flight >= 2                          # genuinely concurrent


def test_reactive_dedups_and_caps_with_announcement():
    # a reactor that always spawns the same id -> deduped; runaway distinct spawns -> capped.
    def execute(spec):
        return {"id": spec["id"], "n": spec.get("n", 0)}

    def react(result, spec, results):
        return [{"id": "dup"}, {"id": "u" + str(result["n"] + 1), "n": result["n"] + 1}]

    rep = run_reactive([{"id": "u0", "n": 0}], execute, react, concurrency=2, max_tasks=10, spec_key=_key)
    ids = [r["id"] for r in rep.results]
    assert ids.count("dup") == 1                 # deduped despite being spawned every round
    assert rep.dispatched <= 10 and rep.hit_cap  # cap held
    assert any("max_tasks" in c for c in rep.caps_announced)  # announced, not silent


def test_reactive_sequential_still_reacts():
    # concurrency<=1 (thread-unsafe backend) still spawns on the fly, just serially.
    def execute(spec):
        return {"id": spec["id"], "chain": spec.get("chain", 0)}

    def react(result, spec, results):
        c = result["chain"]
        return [{"id": "c" + str(c + 1), "chain": c + 1}] if c < 3 else []

    rep = run_reactive([{"id": "c0", "chain": 0}], execute, react, concurrency=1, spec_key=_key)
    assert rep.dispatched == 4 and rep.peak_in_flight == 1   # c0->c1->c2->c3, serial
    assert {r["id"] for r in rep.results} == {"c0", "c1", "c2", "c3"}


def test_reactive_bad_reactor_does_not_crash():
    def execute(spec):
        return {"id": spec["id"]}

    def react(result, spec, results):
        raise RuntimeError("reactor blew up")

    rep = run_reactive([{"id": "a"}, {"id": "b"}], execute, react, concurrency=2, spec_key=_key)
    assert rep.dispatched == 2 and len(rep.results) == 2     # loop survived a bad reactor


def test_drive_graph_runs_dependents_after_deps_no_barrier():
    # find -> verify -> synth; verify must see find's result, synth must see verify's.
    g = TaskGraph()
    g.add(TaskSpec("find", kind="find"))
    g.add(TaskSpec("verify", deps=("find",), kind="verify"))
    g.add(TaskSpec("synth", deps=("verify",), kind="synth"))
    seen_when = {}

    def dispatch(spec):
        seen_when[spec.id] = {d: g.get(d).status.value for d in spec.deps}
        return spec.id + "-done"

    drive_graph(g, dispatch, concurrency=4)
    assert g.is_complete()
    assert g.get("synth").result == "synth-done"
    assert seen_when["verify"]["find"] == "done"      # dep finished before dependent ran
    assert seen_when["synth"]["verify"] == "done"


def test_drive_graph_skips_dependents_of_a_failure():
    g = TaskGraph()
    g.add(TaskSpec("a", kind="x"))
    g.add(TaskSpec("b", deps=("a",), kind="x"))   # depends on the one that fails

    def dispatch(spec):
        if spec.id == "a":
            raise ValueError("boom")
        return "ok"

    drive_graph(g, dispatch, concurrency=2)
    assert g.get("a").status.value == "failed"
    assert g.get("b").status.value == "skipped"   # fail-fast skip propagation, no hang


def test_drive_graph_skip_propagation_is_order_independent():
    # regression: a chain a(fail)->b->c->d where c,d are inserted BEFORE their dep b
    # must NOT leave c/d PENDING after the driver returns (fixpoint skip-propagation).
    g = TaskGraph()
    g.add(TaskSpec("a", kind="x"))
    g.add(TaskSpec("d", deps=("c",), kind="x"))   # dependents inserted BEFORE their deps
    g.add(TaskSpec("c", deps=("b",), kind="x"))
    g.add(TaskSpec("b", deps=("a",), kind="x"))

    def dispatch(spec):
        if spec.id == "a":
            raise ValueError("boom")
        return "ok"

    drive_graph(g, dispatch, concurrency=4)
    # assert BEFORE is_complete() — the driver itself must have resolved the tail
    assert g.get("a").status.value == "failed"
    assert g.get("b").status.value == "skipped"
    assert g.get("c").status.value == "skipped"   # was leaking PENDING pre-fix
    assert g.get("d").status.value == "skipped"
