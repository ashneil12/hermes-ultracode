"""Scale/correctness tests for the orchestration machinery (fast, no API)."""

from bench.stress import probe


def test_100_agents_complete_and_parallel():
    r = probe(100, cap=10, concurrency=100, latency=0.02)
    assert r["returned"] == 100
    assert r["indices_complete"] and r["unique"]
    # true parallelism: peak must be far above the per-call cap
    assert r["peak_concurrency"] >= 50, r


def test_high_concurrency_through_small_per_call_cap():
    # backend caps each call at 3, but we still want ~100 in flight via concurrent waves
    r = probe(100, cap=3, concurrency=99, latency=0.02)
    assert r["returned"] == 100 and r["indices_complete"]
    assert r["peak_concurrency"] >= 40, r


def test_sequential_when_concurrency_equals_cap():
    r = probe(60, cap=10, concurrency=10, latency=0.01)
    assert r["returned"] == 60 and r["indices_complete"]
    # sequential waves -> peak stays near the per-call cap, not 60
    assert r["peak_concurrency"] <= 20, r


def test_failures_are_graceful_at_scale():
    r = probe(200, cap=5, concurrency=200, latency=0.01, failure_rate=0.15)
    assert r["returned"] == 200 and r["indices_complete"]  # nothing lost
    assert r["errors"] > 0  # failures surfaced, not swallowed


def test_600_agents_hold_together():
    # latency high enough that tasks stay in-flight and the pool actually fills
    # (avoids a timing-flaky peak); the point is correctness + >>cap parallelism.
    r = probe(600, cap=8, concurrency=200, latency=0.03)
    assert r["returned"] == 600 and r["indices_complete"] and r["unique"]
    assert r["peak_concurrency"] >= 100, r  # 12x+ the per-call cap of 8
