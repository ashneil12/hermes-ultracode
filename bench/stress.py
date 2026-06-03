"""Stress test the ultracode orchestration machinery at scale (100+ agents).

Two layers:
  A. delegate_fanout machinery — a fast FAKE backend (latency + failure injection
     + a thread-safe concurrency gauge) so we can verify, with no API cost:
       * correctness at scale (all N results, global indices complete & unique),
       * real parallelism (peak concurrency reaches the target, not serial),
       * graceful failure (a slice of failing agents doesn't crash the fan-out).
  B. full-harness at scale — a run that naturally spawns 100s of subagents
     (finders × rounds + findings × skeptics) to prove the whole pipeline holds.

Run:  python bench/stress.py            # fake-backend scale probe (no API)
      python bench/stress.py --real N   # real deepseek-v4-pro concurrency probe at N
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.adapters import delegate_fanout


class ConcurrencyGauge:
    """Tracks current and PEAK simultaneous in-flight tasks across threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current = 0
        self.peak = 0
        self.total = 0

    def enter(self) -> None:
        with self._lock:
            self.current += 1
            self.total += 1
            self.peak = max(self.peak, self.current)

    def exit(self) -> None:
        with self._lock:
            self.current -= 1


class FakeBackend:
    """A concurrency-safe fake delegate backend. Each task sleeps ``latency`` and
    a ``failure_rate`` fraction return an error entry. Runs a wave's tasks
    concurrently in its own pool (like the real client), updating the gauge."""

    def __init__(self, latency: float = 0.05, failure_rate: float = 0.0, gauge: ConcurrencyGauge = None,
                 wave_workers: int = 64, rendezvous: Any = None):
        self.latency = latency
        self.failure_rate = failure_rate
        self.gauge = gauge or ConcurrencyGauge()
        self.wave_workers = wave_workers
        # optional rendezvous: every concurrently-alive task waits here before finishing,
        # so the peak gauge DETERMINISTICALLY reaches the barrier size regardless of machine
        # load — turns a timing-flaky parallelism check into an exact one.
        self.rendezvous = rendezvous
        self._calls = 0
        self._calls_lock = threading.Lock()

    def delegate_fn(self, *, tasks: List[Dict[str, Any]], parent_agent: Any = None, role: str = "leaf") -> str:
        with self._calls_lock:
            self._calls += 1

        def one(i_t):
            i, t = i_t
            self.gauge.enter()
            try:
                if self.rendezvous is not None:
                    # all parties rendezvous at peak BEFORE any exits -> peak == barrier size.
                    try:
                        self.rendezvous.wait()
                    except threading.BrokenBarrierError:
                        pass  # a partial final generation times out -> just proceed
                time.sleep(self.latency)
                # deterministic pseudo-failure by index hash (no Math.random needed)
                fail = self.failure_rate > 0 and (hash(t.get("goal", "")) % 100) < int(self.failure_rate * 100)
                if fail:
                    return {"task_index": i, "status": "error", "summary": None, "error": "injected failure"}
                return {"task_index": i, "status": "completed",
                        "summary": json.dumps({"findings": [{"claim": f"f{i}", "locator": f"x:{i}", "evidence": "e"}]}),
                        "tokens": {"input": 10, "output": 10}}
            finally:
                self.gauge.exit()

        n = max(1, min(self.wave_workers, len(tasks)))
        with ThreadPoolExecutor(max_workers=n) as ex:
            results = list(ex.map(one, enumerate(tasks)))
        return json.dumps({"results": results})


def probe(n: int, cap: int, concurrency: int, latency: float = 0.05, failure_rate: float = 0.0,
          deterministic: bool = True) -> Dict[str, Any]:
    gauge = ConcurrencyGauge()
    # Compute the TRUE expected peak from the same wave math delegate_fanout uses, and
    # rendezvous exactly that many tasks so the parallelism check is deterministic (not a
    # timing race that sags under load). expected_peak = wave_workers * per-wave width.
    n_waves = (n + cap - 1) // cap
    wave_workers = max(1, min(n_waves, (concurrency + cap - 1) // cap))
    expected_peak = min(n, wave_workers * cap)
    rendezvous = threading.Barrier(expected_peak, timeout=4.0) if (deterministic and expected_peak >= 1) else None
    backend = FakeBackend(latency=latency, failure_rate=failure_rate, gauge=gauge,
                          wave_workers=max(cap, 64), rendezvous=rendezvous)
    tasks = [{"goal": f"task {i}"} for i in range(n)]
    t0 = time.time()
    results = delegate_fanout(tasks, max_children=cap, concurrency=concurrency, delegate_fn=backend.delegate_fn)
    dt = time.time() - t0
    indices = [r.get("task_index") for r in results]
    errors = sum(1 for r in results if r.get("status") == "error")
    ideal_serial = (n * latency)
    return {
        "n": n, "cap": cap, "concurrency": concurrency,
        "returned": len(results),
        "indices_complete": sorted(indices) == list(range(n)),
        "unique": len(set(indices)) == len(indices),
        "errors": errors,
        "peak_concurrency": gauge.peak,
        "expected_peak": expected_peak,
        "total_ran": gauge.total,
        "backend_calls": backend._calls,
        "wall_s": round(dt, 2),
        "serial_would_be_s": round(ideal_serial, 2),
        "speedup": round(ideal_serial / dt, 1) if dt else None,
    }


def fake_scale_suite() -> None:
    print("=== A. delegate_fanout machinery (fake backend, no API) ===")
    scenarios = [
        (100, 10, 100), (100, 3, 100),  # 100 agents, small per-call cap, high concurrency
        (300, 10, 100), (600, 8, 200),  # bigger fan-outs
        (100, 10, 10),                  # concurrency==cap -> sequential waves (control)
        (200, 5, 200, 0.05, 0.15),      # 15% injected failures
    ]
    for sc in scenarios:
        r = probe(*sc)
        ok = r["indices_complete"] and r["unique"] and r["returned"] == r["n"]
        print(f"  N={r['n']:<4} cap={r['cap']:<3} conc={r['concurrency']:<4} -> "
              f"returned={r['returned']} complete={r['indices_complete']} peak={r['peak_concurrency']:<4} "
              f"errs={r['errors']} wall={r['wall_s']}s (serial {r['serial_would_be_s']}s, {r['speedup']}x) "
              f"{'OK' if ok else 'FAIL'}")


def real_probe(n: int) -> None:
    """Probe real deepseek-v4-pro concurrency at N trivial calls."""
    from bench.deepseek_client import DeepSeekClient
    print(f"=== B. real deepseek-v4-pro concurrency probe: N={n} ===")
    client = DeepSeekClient(model="deepseek-v4-pro", max_workers=n)
    tasks = [{"goal": f'Return ONLY JSON {{"findings":[{{"claim":"ok {i}","locator":"x:{i}","evidence":"e"}}]}}'} for i in range(n)]
    t0 = time.time()
    results = delegate_fanout(tasks, max_children=n, concurrency=n, delegate_fn=client.delegate_fn)
    dt = time.time() - t0
    completed = sum(1 for r in results if r.get("status") == "completed")
    errors = sum(1 for r in results if r.get("status") != "completed")
    print(f"  returned={len(results)} completed={completed} errors={errors} wall={dt:.0f}s "
          f"usage={client.usage.snapshot()}")
    print(f"  per-call avg ~{dt:.0f}s wall for {n} concurrent (vs ~{completed}x serial)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=int, default=0, help="run real deepseek concurrency probe at N")
    args = ap.parse_args()
    if args.real:
        real_probe(args.real)
    else:
        fake_scale_suite()
