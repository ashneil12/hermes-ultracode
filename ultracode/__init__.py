"""ultracode — a deterministic orchestration harness for the Hermes agent.

Ports the Claude Code "ultracode" effort mode into Hermes: maximum reasoning
budget + deterministic multi-agent orchestration + a *standing* behavioral
stance that the harness ENFORCES rather than hoping the model honors a sentence.

The package is layered so the cognitive value-add is testable without a live
model — every module that touches the fork (delegate_task, auxiliary_client,
reasoning_config) is reached through ``adapters`` with dependency-injection
seams, so unit tests pass fakes and never import the heavy runtime.

Layers
------
schema   : data contracts (Finding, Verdict, StageResult, shapes) — pure stdlib.
graph    : a clean DAG chassis (spec/run/status, cycle validation, ready-queue).
adapters : DI wrappers over delegate_task / call_llm + a robust JSON extractor.
config   : UltracodeConfig + loader (effort, caps, quorum, budgets).
steering : the doctrine encoded as decision functions (the BRAIN).         [phase 2]
pipeline : no-barrier driver over the delegate executor.                   [phase 2]
verify   : adversarial skeptic pool (default-refuted, lens-diverse).        [phase 2]
discovery: loop-until-dry controller.                                       [phase 2]
critic   : completeness critic + judge panel.                              [phase 2]
planner  : PLAN(tools-off) -> scale-to-the-ask gate.                        [phase 2]
mode     : cache-safe standing injection + /ultracode toggle.              [phase 3]
ledger   : durable JSONL run record.                                       [phase 4]

Design provenance: distilled from an adversarial review of 12 upstream
hermes-agent PRs (none of which implemented the cognitive layer) plus a
scenario-sampled "steering doctrine". See DOCTRINE.md and CONTRACTS.md.
"""

__version__ = "0.1.0-dev"

from ultracode.schema import (  # noqa: F401
    Finding,
    OrchestrationShape,
    StageResult,
    SubtaskSpec,
    Verdict,
    VerifyLens,
    VerifierVote,
    dedupe_findings,
)

__all__ = [
    "__version__",
    "Finding",
    "OrchestrationShape",
    "StageResult",
    "SubtaskSpec",
    "Verdict",
    "VerifyLens",
    "VerifierVote",
    "dedupe_findings",
]
