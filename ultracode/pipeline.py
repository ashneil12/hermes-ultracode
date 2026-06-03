"""pipeline.py — the no-barrier, REACTIVE orchestration driver.

The driver graph.py's docstring points to, finally written. Two capabilities, one loop —
the thing that lets the orchestrator SPAWN AGENTS ON THE FLY as results come back instead
of waiting for a whole batch:

  run_reactive(seeds, execute, react, ...)
      A GROWING frontier. Dispatch workers; as EACH one returns, call react(result) which
      may enqueue NEW workers that enter the pool IMMEDIATELY — while the others are still
      running. This is "agent #3 came back with something surprising, so spawn two more to
      chase it, before #5–10 even finish." No round barrier; the work-list grows live.

  drive_graph(graph, dispatch, ...)
      A no-barrier DAG driver over TaskGraph: a node runs the instant ITS OWN deps finish
      (graph.ready()), not when a whole stage does — so a 'verify' starts while other
      'find' nodes are still in flight (find→verify→synth overlap, no global barrier).

Both DEGRADE to sequential-but-still-reactive when concurrency is None/<=1 (the real-Hermes
thread-unsafe backend): each completion is still processed — and can still spawn — before
the next dispatch. Reactivity is independent of parallelism; the barrier was the only thing
in the way, and that's what this removes.
"""

from __future__ import annotations

import concurrent.futures as _cf
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional


@dataclass
class ReactiveReport:
    results: List[Any] = field(default_factory=list)
    dispatched: int = 0          # total workers run (seeds + on-the-fly spawns)
    spawned: int = 0             # workers added reactively (not seeds)
    peak_in_flight: int = 0      # max concurrent workers (proves real parallelism)
    hit_cap: bool = False
    caps_announced: List[str] = field(default_factory=list)


def run_reactive(
    seeds: List[Any],
    execute: Callable[[Any], Any],
    react: Callable[[Any, Any, List[Any]], Optional[List[Any]]],
    *,
    concurrency: Optional[int] = 8,
    max_tasks: int = 500,
    spec_key: Optional[Callable[[Any], Any]] = None,
) -> ReactiveReport:
    """Event-driven orchestration with on-the-fly spawning.

    ``execute(spec) -> result`` runs one worker. ``react(result, spec, results_so_far)``
    is called the instant that worker returns and may return a list of NEW specs to run;
    they enter the pool immediately (mid-flight), so the work-list adapts to evidence as
    it arrives rather than round-by-round. ``spec_key`` dedupes spawns (default: identity);
    ``max_tasks`` is an announced safety bound against runaway spawning.
    """
    key = spec_key or (lambda s: id(s))
    frontier: Deque[Any] = deque(seeds)
    seen = {key(s) for s in seeds}
    rep = ReactiveReport()

    def _absorb(result: Any, spec: Any) -> None:
        rep.results.append(result)
        try:
            fresh = react(result, spec, rep.results) or []
        except Exception:
            fresh = []  # a bad reactor never crashes the loop
        for ns in fresh:
            k = key(ns)
            if k in seen:
                continue
            if rep.dispatched + len(frontier) >= max_tasks:
                rep.hit_cap = True
                continue
            seen.add(k)
            frontier.append(ns)          # <-- the on-the-fly spawn
            rep.spawned += 1

    # --- sequential but STILL reactive (thread-unsafe backend / concurrency<=1) ----
    if concurrency is None or concurrency <= 1:
        while frontier and rep.dispatched < max_tasks:
            spec = frontier.popleft()
            rep.dispatched += 1
            rep.peak_in_flight = max(rep.peak_in_flight, 1)
            try:
                res = execute(spec)
            except Exception as exc:
                res = {"error": str(exc), "spec": spec}
            _absorb(res, spec)           # may enqueue before the next dispatch
        _announce_cap(rep, max_tasks)
        return rep

    # --- concurrent + STREAMING: process completions as they arrive ---------------
    with _cf.ThreadPoolExecutor(max_workers=int(concurrency)) as ex:
        in_flight: Dict[_cf.Future, Any] = {}

        def _fill() -> None:
            while frontier and len(in_flight) < int(concurrency) and rep.dispatched < max_tasks:
                spec = frontier.popleft()
                rep.dispatched += 1
                in_flight[ex.submit(execute, spec)] = spec
            rep.peak_in_flight = max(rep.peak_in_flight, len(in_flight))

        _fill()
        while in_flight:
            done, _ = _cf.wait(list(in_flight), return_when=_cf.FIRST_COMPLETED)
            for fut in done:
                spec = in_flight.pop(fut)
                try:
                    res = fut.result()
                except Exception as exc:
                    res = {"error": str(exc), "spec": spec}
                _absorb(res, spec)        # react() may enqueue new specs
            _fill()                       # spawns + refills enter the pool NOW (mid-flight)
    _announce_cap(rep, max_tasks)
    return rep


def _announce_cap(rep: ReactiveReport, max_tasks: int) -> None:
    if rep.hit_cap:
        rep.caps_announced.append(
            f"reactive scheduler hit max_tasks={max_tasks}; further on-the-fly spawns dropped (announced)")


def drive_graph(
    graph: Any,
    dispatch: Callable[[Any], Any],
    *,
    concurrency: Optional[int] = 8,
) -> Any:
    """Run a TaskGraph with NO global barriers: each node runs the instant its own deps
    finish (graph.ready()), not when a whole stage does. ``dispatch(spec) -> result``.
    A node whose dep failed is auto-SKIPPED by the graph. Returns the graph (mutated)."""
    graph.validate()

    if concurrency is None or concurrency <= 1:
        while not graph.is_complete():
            ready = graph.ready()
            if not ready:
                break
            for run in ready:
                graph.mark_running(run.spec.id)
                try:
                    graph.mark_done(run.spec.id, dispatch(run.spec))
                except Exception as exc:
                    graph.mark_failed(run.spec.id, str(exc))
        return graph

    with _cf.ThreadPoolExecutor(max_workers=int(concurrency)) as ex:
        in_flight: Dict[_cf.Future, str] = {}

        def _launch() -> None:
            for run in graph.ready():
                graph.mark_running(run.spec.id)
                in_flight[ex.submit(dispatch, run.spec)] = run.spec.id

        _launch()
        while in_flight:
            done, _ = _cf.wait(list(in_flight), return_when=_cf.FIRST_COMPLETED)
            for fut in done:
                tid = in_flight.pop(fut)
                try:
                    graph.mark_done(tid, fut.result())
                except Exception as exc:
                    graph.mark_failed(tid, str(exc))
            _launch()                     # deps just satisfied -> newly-ready nodes launch NOW
    return graph
