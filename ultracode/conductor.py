"""conductor.py — the session-level executive loop, as real control structures.

This is the layer above steering.py: where steering decides ONE run, the
conductor runs continuously across turns, re-deciding the plan as evidence streams
in. It is re-entered on exactly two events — a returned subagent result, and a new
user message — and on each entry it re-derives rather than resumes.

It is deliberately a FRAMEWORK, not a driver: the actual workflow dispatch lives
in the host runtime. What lives here is the part the doctrine insists must be
*binding* — the gates, the constraint registry, the governors — "a place where
the harness can BLOCK or REDIRECT" (DOCTRINE.md Part III). Everything is
deterministic and unit-tested with no model.

Mapping to the executive spec (see DOCTRINE.md Part III & the executive analysis):
  - ignition gate        -> classify() + ExecutiveDecision
  - cross-turn frontier  -> self.frontier (a session-scope TaskGraph)
  - fold-constraints      -> ConstraintRegistry consulted on every spawn
  - governors             -> run_governors() returning binding signals
  - session reversibility -> last_green_commit + deferred_actions register
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ultracode.config import UltracodeConfig
from ultracode.graph import TaskGraph, TaskSpec
from ultracode.steering import TurnClass, classify_turn


class ExecutiveAction(str, Enum):
    SUPPRESS = "suppress"          # conversational/trivial -> answer solo, mint no run
    SCOUT_FIRST = "scout_first"    # build/feasibility -> a cheap probe must precede expensive nodes
    ORCHESTRATE = "orchestrate"    # authorized to create expensive nodes
    RESCOPE = "rescope"            # new user signal -> fork the frontier, don't replace
    COLLAPSE = "collapse"          # budget -> coarsen a fan-out to solo
    PREEMPT = "preempt"            # flat progress -> kill a stalled node
    OFFLOAD = "offload"            # large output -> spill to disk, don't narrate
    ABANDON = "abandon"            # premise dead -> rollback to last green
    ASK_HUMAN = "ask_human"        # batched forking decisions -> one question


@dataclass
class ExecutiveDecision:
    action: ExecutiveAction
    reason: str
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Constraint:
    """A runtime-learned fact that mechanically re-routes future spawns."""
    kind: str          # e.g. "max_concurrent_children", "call_llm_threadunsafe", "max_spawn_depth"
    value: Any
    reason: str = ""


class ConstraintRegistry:
    def __init__(self) -> None:
        self._c: Dict[str, Constraint] = {}

    def fold(self, kind: str, value: Any, reason: str = "") -> Constraint:
        c = Constraint(kind, value, reason)
        self._c[kind] = c
        return c

    def get(self, kind: str, default: Any = None) -> Any:
        c = self._c.get(kind)
        return c.value if c else default

    def all(self) -> List[Constraint]:
        return list(self._c.values())


@dataclass
class Intent:
    goal: str
    seq: int


@dataclass
class Meters:
    tokens: int = 0
    wall_clock_s: float = 0.0
    window_chars: int = 0

    def spend(self, tokens: int = 0, seconds: float = 0.0) -> None:
        self.tokens += int(tokens)
        self.wall_clock_s += float(seconds)


# A governor reads the controller and either fires a binding signal or returns None.
Governor = Callable[["SessionController"], Optional[ExecutiveDecision]]


class SessionController:
    """The conductor. Created ONCE per session; outlives any single /ultracode run.

    Typical loop (host-driven):
        sc = SessionController(cfg)
        dec = sc.on_user_message(text)        # ignition gate
        ... if dec.action == ORCHESTRATE: build frontier nodes, dispatch ...
        sc.on_result(node_id, result, spend)  # reconcile + meter
        for sig in sc.run_governors(): ...     # preempt/collapse/offload/...
    """

    OFFLOAD_WATERMARK_CHARS = 24_000

    def __init__(self, config: Optional[UltracodeConfig] = None):
        self.config = config or UltracodeConfig()
        self.frontier = TaskGraph()
        self.intents: List[Intent] = []
        self.constraints = ConstraintRegistry()
        self.meters = Meters()
        self.deferred_actions: List[str] = []   # known-but-unactionable corrections
        self.open_fork_questions: List[str] = []
        self.last_green_commit: Optional[str] = None
        self._seq = 0
        self._working_goal: Optional[str] = None
        self.log: List[str] = []

    # ---- ignition gate ----------------------------------------------------
    def classify(self, text: str) -> str:
        return classify_turn(text)

    def on_user_message(self, text: str) -> ExecutiveDecision:
        """The ignition gate. Conversational -> suppress (no machinery). Build ->
        require a scout precondition. A non-first message FORKS the frontier."""
        self._seq += 1
        turn = self.classify(text)
        if turn == TurnClass.CONVERSATIONAL:
            self._note(f"suppressed:trivial seq={self._seq}")
            return ExecutiveDecision(ExecutiveAction.SUPPRESS, "conversational/trivial turn — answer solo, mint no run")
        # a new sanctioned goal forks, never replaces
        forked = len(self.intents) > 0
        self.intents.append(Intent(goal=text, seq=self._seq))
        self._working_goal = text
        if forked:
            self._note(f"goal_revised seq={self._seq} (forked, {len(self.intents)} intents live)")
            return ExecutiveDecision(ExecutiveAction.RESCOPE, "new user signal — fork the frontier, preserve in-flight",
                                     {"intents": len(self.intents)})
        return ExecutiveDecision(ExecutiveAction.SCOUT_FIRST, "build/feasibility turn — a cheap scout must authorize expensive nodes")

    def spawn_allowed(self, kind: str, deps: tuple) -> bool:
        """Scout-gate as a typed precondition: an EXPENSIVE node may not have empty
        deps — something cheap must have authorized it first. Cheap kinds (scout,
        classify) are exempt."""
        if kind in ("scout", "classify", "probe"):
            return True
        return len(deps) > 0  # expensive node requires an authorizing predecessor

    def authorize_node(self, spec: TaskSpec):
        if not self.spawn_allowed(spec.kind, spec.deps):
            raise ValueError(f"spawn blocked: expensive node {spec.id!r} ({spec.kind}) has no authorizing scout/deps")
        return self.frontier.add(spec)

    # ---- evidence reconciliation + metering ------------------------------
    def on_result(self, node_id: str, result: Any = None, *, tokens: int = 0, seconds: float = 0.0,
                  output_chars: int = 0) -> None:
        if node_id in [s for s in getattr(self.frontier, "_runs", {})]:
            self.frontier.mark_done(node_id, result)
        self.meters.spend(tokens, seconds)
        self.meters.window_chars = output_chars

    def fold_constraint(self, kind: str, value: Any, reason: str = "") -> Constraint:
        c = self.constraints.fold(kind, value, reason)
        self._note(f"constraint:{kind}={value} ({reason})")
        return c

    def defer(self, action: str) -> None:
        """Register a known-but-unactionable correction (e.g. the Opus-4.8 gap),
        carried across the session and surfaced at phase boundaries."""
        self.deferred_actions.append(action)

    def set_green(self, commit: str) -> None:
        self.last_green_commit = commit

    # ---- governors (binding control) -------------------------------------
    def run_governors(self) -> List[ExecutiveDecision]:
        out: List[ExecutiveDecision] = []
        for gov in self._governors():
            sig = gov(self)
            if sig is not None:
                out.append(sig)
                self._note(f"governor:{sig.action.value} — {sig.reason}")
        return out

    def _governors(self) -> List[Governor]:
        return [_budget_governor, _context_governor, _frame_validity_governor]

    # ---- internals --------------------------------------------------------
    def _note(self, msg: str) -> None:
        self.log.append(msg)


# ---- governor implementations (pure functions of the controller) ----------

def _budget_governor(sc: SessionController) -> Optional[ExecutiveDecision]:
    cap = sc.config.run_budget_tokens
    if cap and sc.meters.tokens >= cap:
        return ExecutiveDecision(
            ExecutiveAction.COLLAPSE,
            f"cumulative spend {sc.meters.tokens} >= run_budget_tokens {cap} — collapse to coarser shape",
            {"tokens": sc.meters.tokens, "cap": cap, "announced": True},
        )
    return None


def _context_governor(sc: SessionController) -> Optional[ExecutiveDecision]:
    if sc.meters.window_chars >= sc.OFFLOAD_WATERMARK_CHARS:
        return ExecutiveDecision(
            ExecutiveAction.OFFLOAD,
            f"tool output {sc.meters.window_chars} chars >= watermark {sc.OFFLOAD_WATERMARK_CHARS} — spill to disk, admit a digest",
            {"chars": sc.meters.window_chars},
        )
    return None


def _frame_validity_governor(sc: SessionController) -> Optional[ExecutiveDecision]:
    # fires only on UNLOGGED drift: working goal diverged from the sanctioned top
    # intent with no 'goal_revised' event. (Intended re-scopes log goal_revised.)
    if not sc.intents or sc._working_goal is None:
        return None
    top = sc.intents[-1].goal
    if sc._working_goal != top and not any("goal_revised" in m for m in sc.log[-3:]):
        return ExecutiveDecision(
            ExecutiveAction.RESCOPE,
            "working goal diverged from last sanctioned goal without a logged cause — halt and reconcile",
            {"working": sc._working_goal[:60], "sanctioned": top[:60]},
        )
    return None
