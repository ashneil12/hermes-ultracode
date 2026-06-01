"""A clean, stdlib-only DAG chassis for staged orchestration.

This is the bookkeeping layer: it knows task identity, dependencies, status,
cycle-validity, and which tasks are *ready* to run. It does NOT run anything —
execution is the pipeline driver's job (pipeline.py), which submits ready tasks
onto the existing delegate executor and feeds results back here.

Why our own instead of lifting upstream PR #12436's task_graph.py: that file
lived under a foreign ``src/orchestration/`` layout, mutated ``os.environ``
(thread-unsafe under concurrent fan-out), hardcoded ``payload['results'][0]``
parsing, and barriered every wave with ``asyncio.gather``. We keep its good idea
(a frozen spec + indegree ready-queue + fail-fast skip propagation) and drop the
bugs. The ready-queue is the seam that lets pipeline.py avoid global barriers:
a task becomes ready the instant *its own* deps finish, not when a whole wave does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"  # an upstream dep failed; this can never run


_TERMINAL = (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.SKIPPED)


@dataclass(frozen=True)
class TaskSpec:
    """An immutable node. ``kind`` lets the driver dispatch (e.g. 'find',
    'verify', 'synthesize'); ``payload`` carries stage-specific data."""

    id: str
    deps: Tuple[str, ...] = ()
    kind: str = "task"
    payload: Dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass
class TaskRun:
    spec: TaskSpec
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None


class GraphError(ValueError):
    """Raised on structural problems: duplicate ids, unknown deps, or cycles."""


class TaskGraph:
    """A validated dependency graph with an indegree-seeded ready-queue.

    Typical use::

        g = TaskGraph()
        g.add(TaskSpec("find"))
        g.add(TaskSpec("verify", deps=("find",)))
        g.add(TaskSpec("synth", deps=("verify",)))
        g.validate()
        while not g.is_complete():
            for run in g.ready():            # only tasks whose deps are DONE
                g.mark_running(run.spec.id)
                ...                          # driver executes (possibly async)
                g.mark_done(run.spec.id, result)
    """

    def __init__(self) -> None:
        self._runs: Dict[str, TaskRun] = {}
        self._order: List[str] = []  # insertion order, for stable iteration
        self._validated = False

    # ---- construction -----------------------------------------------------
    def add(self, spec: TaskSpec) -> TaskRun:
        if spec.id in self._runs:
            raise GraphError(f"duplicate task id: {spec.id!r}")
        run = TaskRun(spec=spec)
        self._runs[spec.id] = run
        self._order.append(spec.id)
        self._validated = False
        return run

    def add_many(self, specs: Iterable[TaskSpec]) -> None:
        for s in specs:
            self.add(s)

    # ---- validation -------------------------------------------------------
    def validate(self) -> "TaskGraph":
        # unknown deps
        for rid in self._order:
            for dep in self._runs[rid].spec.deps:
                if dep not in self._runs:
                    raise GraphError(f"task {rid!r} depends on unknown task {dep!r}")
                if dep == rid:
                    raise GraphError(f"task {rid!r} depends on itself")
        # cycle detection via Kahn's algorithm
        indeg = {rid: len(self._runs[rid].spec.deps) for rid in self._order}
        dependents: Dict[str, List[str]] = {rid: [] for rid in self._order}
        for rid in self._order:
            for dep in self._runs[rid].spec.deps:
                dependents[dep].append(rid)
        queue = [rid for rid in self._order if indeg[rid] == 0]
        visited = 0
        while queue:
            n = queue.pop()
            visited += 1
            for m in dependents[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if visited != len(self._order):
            stuck = [rid for rid in self._order if indeg[rid] > 0]
            raise GraphError(f"cycle detected among tasks: {sorted(stuck)}")
        self._validated = True
        return self

    # ---- scheduling -------------------------------------------------------
    def ready(self) -> List[TaskRun]:
        """Tasks whose every dependency is DONE and that haven't started.

        A dep that FAILED/SKIPPED does NOT make a task ready — it makes it
        SKIPPED (fail-fast). We surface that here so the driver never blocks
        on something that can never run."""
        if not self._validated:
            self.validate()
        out: List[TaskRun] = []
        for rid in self._order:
            run = self._runs[rid]
            if run.status != TaskStatus.PENDING:
                continue
            dep_statuses = [self._runs[d].status for d in run.spec.deps]
            if any(s in (TaskStatus.FAILED, TaskStatus.SKIPPED) for s in dep_statuses):
                run.status = TaskStatus.SKIPPED
                run.error = "skipped: an upstream dependency did not complete"
                continue
            if all(s == TaskStatus.DONE for s in dep_statuses):
                run.status = TaskStatus.READY
                out.append(run)
        return out

    def mark_running(self, task_id: str) -> None:
        self._runs[task_id].status = TaskStatus.RUNNING

    def mark_done(self, task_id: str, result: Any = None) -> None:
        run = self._runs[task_id]
        run.status = TaskStatus.DONE
        run.result = result

    def mark_failed(self, task_id: str, error: str = "") -> None:
        run = self._runs[task_id]
        run.status = TaskStatus.FAILED
        run.error = error or "failed"

    # ---- queries ----------------------------------------------------------
    def get(self, task_id: str) -> TaskRun:
        return self._runs[task_id]

    def is_complete(self) -> bool:
        """True once every task is terminal. Calling ``ready()`` first lets
        skip-propagation settle, so an all-skipped tail still completes."""
        if not self._validated:
            self.validate()
        self.ready()  # let skip propagation resolve newly-unreachable tasks
        return all(r.status in _TERMINAL for r in self._runs.values())

    def results(self) -> Dict[str, Any]:
        return {rid: r.result for rid, r in self._runs.items() if r.status == TaskStatus.DONE}

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._runs.values():
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
        return counts

    def topo_order(self) -> List[str]:
        """Deterministic topological order (stable by insertion order)."""
        if not self._validated:
            self.validate()
        indeg = {rid: len(self._runs[rid].spec.deps) for rid in self._order}
        dependents: Dict[str, List[str]] = {rid: [] for rid in self._order}
        for rid in self._order:
            for dep in self._runs[rid].spec.deps:
                dependents[dep].append(rid)
        ready = [rid for rid in self._order if indeg[rid] == 0]
        out: List[str] = []
        while ready:
            ready.sort(key=lambda r: self._order.index(r))
            n = ready.pop(0)
            out.append(n)
            for m in dependents[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
        return out

    def __len__(self) -> int:
        return len(self._runs)
