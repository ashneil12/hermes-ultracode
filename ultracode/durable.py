"""durable.py — optional bridge from an ultracode run onto Hermes's shipped kanban swarm.

A foreground ultracode run is turn-scoped: it dies on /stop or /new with its in-memory task graph
lost. Hermes already ships a DURABLE multi-agent kernel (``hermes_cli/kanban_swarm.py``) whose topology
— root → parallel workers → verifier → synthesizer, on a SQLite-backed shared blackboard, recoverable
from the root — is exactly the shape this harness builds. So durability is not a rebuild: it is mapping
our ``SubtaskSpec`` workers onto ``kanban_swarm.create_swarm`` and letting the kernel persist + resume.

This bridge is OPTIONAL and lazily-bound: it imports the host module only when asked, so the package
stays standalone/testable. ``kanban_available()`` reports whether the host has it; ``persist_as_swarm``
does the mapping (with an injectable ``create_fn``/``conn_fn`` seam, like adapters.py, so it's testable
with no Hermes). When the host lacks kanban, callers keep the in-turn path — durability is a graceful
upgrade, never a hard dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ultracode.schema import SubtaskSpec


# The real host contract (verified against hermes_cli/kanban_swarm.py on upstream/main):
#   SwarmWorkerSpec(profile: str, title: str, body: str, skills=[], priority=0, max_runtime_seconds=None)
#   create_swarm(conn, *, goal, workers, verifier_assignee, synthesizer_assignee, root_title=None,
#                verifier_title=..., synthesizer_title=..., created_by=..., ...) -> SwarmCreated
#   SwarmCreated(root_id, worker_ids, verifier_id, synthesizer_id).as_dict()
_DEFAULT_PROFILE = "leaf"


@dataclass
class SwarmHandle:
    """What a durable swarm creation returns: the root card id (shared blackboard / audit anchor),
    the worker card ids, the verifier/synthesizer card ids, and the raw host payload."""
    root_id: str
    worker_ids: List[str]
    verifier_id: str = ""
    synthesizer_id: str = ""
    raw: Dict[str, Any] = None  # type: ignore


def kanban_available() -> bool:
    """True if the host ships the kanban swarm kernel (so the durable path is usable)."""
    try:
        import hermes_cli.kanban_swarm  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def _worker_spec(spec_cls: Any, st: SubtaskSpec, idx: int, profile: str) -> Any:
    """Map one ultracode SubtaskSpec onto the host's ``SwarmWorkerSpec(profile, title, body)``."""
    title = (st.label or st.goal[:60]).strip() or f"worker {idx}"
    body = st.goal if not st.context else f"{st.goal}\n\nCONTEXT:\n{st.context}"
    return spec_cls(profile=profile, title=title, body=body)


def persist_as_swarm(
    goal: str,
    subtasks: List[SubtaskSpec],
    *,
    verifier_assignee: str,
    synthesizer_assignee: str,
    conn: Any = None,
    worker_profile: str = _DEFAULT_PROFILE,
    create_fn: Optional[Callable[..., Any]] = None,
    spec_cls: Any = None,
    verifier_title: str = "Verify swarm outputs",
    synthesizer_title: str = "Synthesize swarm outputs",
    created_by: str = "ultracode",
) -> SwarmHandle:
    """Create a DURABLE kanban swarm (root → workers → verifier → synthesizer) for this run, so it
    survives interruption and can resume. ``verifier_assignee``/``synthesizer_assignee`` are the agent
    profiles the host assigns those cards to (required by ``create_swarm``). ``conn``/``create_fn``/
    ``spec_cls`` are injectable for testing; left None they lazily bind ``hermes_cli.kanban_swarm``
    (raising a clear error if the host lacks it — call ``kanban_available()`` first to choose the
    in-turn path)."""
    if not subtasks:
        raise ValueError("persist_as_swarm requires at least one subtask (the swarm needs ≥1 worker)")
    if create_fn is None or spec_cls is None:
        try:
            from hermes_cli.kanban_swarm import create_swarm as _create, SwarmWorkerSpec as _spec  # type: ignore
        except Exception as exc:  # pragma: no cover - host-dependent
            raise RuntimeError(
                "kanban swarm kernel not available on this host; use the in-turn path "
                "(check durable.kanban_available() before calling persist_as_swarm)") from exc
        create_fn = create_fn or _create
        spec_cls = spec_cls or _spec

    workers = [_worker_spec(spec_cls, st, i, worker_profile) for i, st in enumerate(subtasks)]
    created = create_fn(
        conn, goal=goal, workers=workers,
        verifier_assignee=verifier_assignee, synthesizer_assignee=synthesizer_assignee,
        verifier_title=verifier_title, synthesizer_title=synthesizer_title, created_by=created_by)

    payload = created.as_dict() if hasattr(created, "as_dict") else dict(created or {})
    return SwarmHandle(
        root_id=str(payload.get("root_id") or payload.get("root") or ""),
        worker_ids=[str(w) for w in (payload.get("worker_ids") or payload.get("workers") or [])],
        verifier_id=str(payload.get("verifier_id") or ""),
        synthesizer_id=str(payload.get("synthesizer_id") or ""),
        raw=payload)
