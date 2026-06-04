---
name: dynamic-workflow
description: Orchestrate large fan-out work as a plan-in-code "workflow" so the agent's context holds only the final verified answer, not the exhaust of hundreds of intermediate steps. Use for codebase-wide sweeps, large migrations, multi-angle research, and any task too big for one context window where the split strategy is known enough to script. Includes the adversarial-convergence verification recipe (independent attempts + refuters, keep only surviving claims) and a durable path for runs that must survive interruption.
version: 1.0.0
author: ultracode (adapted from the Hermes + Teknium `dynamic-workflow` skill)
license: MIT
metadata:
  ultracode:
    tags: [orchestration, fan-out, subagents, delegation, verification, migration, audit, research, durability]
when_to_use:
  - A task is too big for one context window AND you can describe the split (per-file, per-endpoint, per-source, per-record)
  - You want orchestration codified as a re-runnable script, not improvised turn-by-turn
  - Quality matters more than token economy: you want independent attempts cross-checked / refuted before you trust the answer
  - Codebase-wide bug/security sweep, 100+ file migration, multi-angle research with sources cross-checked
when_not_to_use:
  - Small bounded task (<~10 units) — call the tool directly or do it inline (discernment routes this to solo)
  - Tight serial dependency (B needs A's output) — orchestration overhead is wasted
  - You need it to survive the user sending a new message — see "Durability" below; an in-turn fan-out is turn-scoped
---

# Dynamic workflow — plan-in-code fan-out with verification

> Credit: this skill adapts the Hermes/Teknium `dynamic-workflow` skill. The mechanic worth copying is
> NOT "more subagents" — it is **moving the plan, the loop, and the intermediate results OUT of the
> context window and INTO a script.** Normally the agent IS the orchestrator and every intermediate
> result piles into context, which is what caps you at a handful of agents. A workflow keeps only the
> *final verified answer* in context; the script (or this harness's `run()`) holds everything else.

This skill maps that pattern onto the ultracode harness's own primitives, so you get the discipline AND
the machinery (deduped union, adversarial verification, retry-the-holes, durability) for free.

## The two layers (pick the right one — they are NOT interchangeable)

| | Layer A: deterministic (a script / `execute_code`) | Layer B: LLM-judgment fan-out |
|---|---|---|
| Use for | fetch N URLs, parse N files, run N shell commands, build the manifest | classify, review, audit, refute, write — per item |
| In ultracode | plain code, or `compute.py` (write+run code, fold the result in as evidence) | `adapters.delegate_fanout` / `corpus.enumerate_corpus` / `corpus.research_corpus` |
| Cost | cheap — tool calls, no per-item LLM | one model-call tree PER child — multiplies linearly |

**Rule of thumb:** do the deterministic part in Layer A FIRST (list the files, extract candidate sites,
write a manifest), then fan out ONLY the irreducibly-LLM step via Layer B. A Layer-A script writes a
manifest; you read it and issue ONE Layer-B fan-out off it.

## The harness already gives you the load-bearing pieces

- **Exhaustive coverage** → `corpus.enumerate_corpus(sections, "every X")`: chunk → one enumerator per
  section → union+dedupe. `retry_empty` re-dispatches any token-starved/flaky chunk so a hole can't
  silently cap recall (the failure that turns "found everything" into a lie). Routes a corpus that fits
  one pass to a single read (no lossy fan-out without a coverage benefit).
- **Output routing** → route structured worker output to FILES, not the `summary` field, which
  truncates under load. The harness's `retry_empty` mitigates the empty case, but for large per-worker
  output, have each child write `out_<i>` and read the files on the parent.
- **Cheaper workers** → `config.worker_model` pins a cheap model on the mechanical finder/extractor
  waves; the planner/synthesis/verify aux calls keep the strong model (weak finders, strong verifier).

## Adversarial convergence (the quality mechanic)

For finding-quality work (security audit, "is this path actually vulnerable?", behavior-preservation):

1. **Independent attempts** — fan out the SAME question to N children with DIFFERENT framings in each
   `context`, so they don't collapse to one line of reasoning. Each emits ATOMIC, LOCATED,
   individually-falsifiable claims (one per line — atomicity is what makes refutation possible).
2. **Count agreement, don't drop it** — `schema.dedupe_findings` now increments `agreement_count` when
   independent finders converge on the same claim (a free confidence prior), instead of discarding.
3. **Refute to convergence** — `verify.verify_to_convergence(findings, rounds=K)`: re-challenge the
   survivors with FRESH independent skeptic passes (give refuters the SOURCES, not the attempts'
   reasoning), default-to-refuted, keep only what survives every round, stop when a round drops nothing.
   `cfg.verify_rounds` sets K (2–3 for high stakes; 1 = single pass).
4. **Atomic or it's theater** — a refuter cannot break "the auth layer has problems"; it CAN break
   "endpoint `POST /users/:id/role` at users.py:142 has no role check." Force located claims.

## Durability (runs that must survive interruption)

An in-turn fan-out is turn-scoped — `/stop` or a new message cancels it. For work that must run across
turns, hand off to the durable swarm: `run(task, durable_conn=<kanban conn>)` (or
`durable.persist_as_swarm(goal, subtasks, ...)`) maps the plan onto the host's SQLite-backed kanban
swarm (root → workers → verifier → synthesizer), which persists and resumes. The harness RETURNS the
swarm handle and does NOT also execute in-turn (or the work would run twice); results accrue on the
swarm blackboard, read back later. When the host lacks kanban, it falls back to the in-turn path and
says so. To resume a previously-interrupted in-turn run, pass `run(..., resume=True, run_id=<same>)` —
it rebuilds findings + the seen-set from the ledger so it doesn't re-derive what was already found.

## Cost discipline (this is the thing that bites)

Each Layer-B child is a full agent tree; 20 children ≈ 20× the model calls, and children inherit the
parent's (expensive) model unless you pin `worker_model`. Always: prove the recipe on a SCOPED slice
(one directory, 20 records, 10 endpoints), report its token cost, THEN offer full scale. Never silently
fan out hundreds of children.

## Verify before you call it done

- Did the deterministic pre-pass run, and does the manifest line-count match the expected unit count?
- Did every fan-out worker contribute (no silent holes)? `enumerate_corpus` announces dropped sections.
- For the verify recipe: can you point to the refuter counter-evidence for every DROPPED claim, and
  confirm every SURFACED claim went through refutation (`verify_rounds`)?
- Did you report token cost on the scoped run before offering full scale?
