---
name: dynamic-workflow
description: Orchestrate large fan-out work as a plan-in-code "workflow" so the agent's context holds only the final verified answer, not the exhaust of hundreds of intermediate steps. Use for codebase-wide sweeps, large migrations, multi-angle research, and any task too big for one context window where the split strategy is known enough to script. Includes the adversarial-convergence verification recipe (independent attempts + refuters, keep only surviving claims).
version: 1.0.0
author: Hermes Agent + Teknium
license: MIT
metadata:
  hermes:
    tags: [orchestration, fan-out, subagents, delegation, verification, migration, audit, research]
    category: autonomous-ai-agents
    related_skills: []
when_to_use:
  - A task is too big for one context window AND you can describe the split (per-file, per-endpoint, per-source, per-record)
  - You want orchestration codified as a re-runnable script, not improvised turn-by-turn
  - Quality matters more than token economy: you want independent attempts cross-checked / refuted before you trust the answer
  - Codebase-wide bug/security sweep, 100+ file migration, multi-angle research with sources cross-checked
when_not_to_use:
  - Small bounded task (<~10 units) — just call the tool directly or do it inline
  - Tight serial dependency (B needs A's output) — orchestration overhead is wasted
  - Reasoning bottleneck, not coverage — the units are independent but the task is multi-hop chaining a weak model can't do; splitting the evidence across children makes the chaining WORSE, not better. Fan out to cover a corpus that exceeds one pass; do NOT fan out to make a weak model reason better (a weak model stays weak), and if a single focused pass already nails it, fan-out is pure cost with no recall gain — a wash.
  - You need it to survive the user sending a new message — see "The synchronous trap" below; use cron/kanban instead
---

# Dynamic Workflow — plan-in-code fan-out with verification

This is Hermes's answer to Claude Code's "dynamic workflows" (run hundreds of
parallel subagents in one session). The mechanic worth copying is NOT "more
subagents" — it is **moving the plan, the loop, and the intermediate results
OUT of the context window and INTO a script.** Normally the agent IS the
orchestrator: every intermediate result piles into context, which is exactly
what caps you at a handful of agents. A workflow keeps only the *final verified
answer* in context; the script holds everything else.

> This skill is self-contained, but it builds on standard fan-out hygiene —
> chunk inputs to ~50-70KB per child, route structured output to files (not the
> `summary` field, which truncates under load), use delimiter-separated lines
> over JSON wrappers, and remember that a "stalled" child often completed its
> write anyway (check the filesystem before retrying). If your install has a
> `delegate-task-output-patterns` skill, load it for the detailed thresholds;
> the rules above are the load-bearing subset.

## The two orchestration-script layers (pick the right one — they are NOT interchangeable)

Hermes has no JS runtime. The "orchestration script" is one of two layers, and
the split is enforced by a real capability boundary, not a style preference:

| | Layer A: `execute_code` (Python script) | Layer B: `delegate_task` batch |
|---|---|---|
| Use for | DETERMINISTIC fan-out — fetch N URLs, parse N files, run N shell commands, template N outputs | LLM-JUDGMENT fan-out — classify, review, decide, write, refute, audit per item |
| The script holds | the loop + branching + intermediate vars (real Python) | n/a — you call it once with a `tasks=[...]` array; each task is its own isolated agent |
| Tools available inside | `web_search, web_extract, read_file, write_file, search_files, terminal, patch` ONLY (the `SANDBOX_ALLOWED_TOOLS` set) | full toolsets per child (configurable) |
| Can it call `delegate_task`? | **NO.** `delegate_task` is NOT in `SANDBOX_ALLOWED_TOOLS`. Do not write a script that imports it — it will fail. | itself, if `role='orchestrator'` and `max_spawn_depth>=2` |
| Concurrency | you control it in Python (`ThreadPoolExecutor`, batches) | `delegation.max_concurrent_children` (default 3; raise in config.yaml) |
| Cost shape | cheap — most steps are tool calls, no per-item LLM unless you call `web_search`/aux | one model call tree PER child task — multiplies linearly, can be very expensive |

**Rule of thumb:** do the deterministic part in Layer A first (inline, in a
script), then fan out ONLY the irreducibly-LLM step via Layer B. This is
Pattern 1 from `delegate-task-output-patterns`, applied at workflow scale.
Mixing them: a Layer-A script can write a manifest file, and you (the parent)
then read that manifest and issue a single Layer-B `delegate_task` batch.

## The synchronous trap (READ THIS — it is the #1 way a "workflow" disappoints)

`delegate_task` runs **synchronously inside the parent turn**. If the user sends
a new message, hits /stop, or /new, every in-flight child is **cancelled and its
work discarded** (status `interrupted`). It does NOT run in the background, and
it does NOT survive the turn. There is no cache-resume of a half-finished fan-out.

So a "workflow" in Hermes is one of:

1. **Foreground workflow (default):** Layer A and/or one Layer-B batch, completed
   within a single turn. Good for minutes-long fan-out (dozens of units). The
   user waits. This is what you build 90% of the time.
2. **Durable workflow (hours/days, survives interruption):** use the **kanban
   swarm** (the SQLite-backed multi-agent kernel that ships with Hermes —
   `hermes_cli/kanban_swarm.py` + the kanban plugin; if your install has a
   `kanban-multiagent` skill, load it for the workflow). It
   writes a task graph (root → parallel workers → verifier → synthesizer) into
   the SQLite kanban kernel with a JSON blackboard. State persists across turns
   and restarts. This is the ONLY path that matches Claude Code's "runs into
   hours and days, resumes where it left off." Reach for it when the foreground
   path would time out or when the user must be able to walk away.

Never promise "background, resumable, hundreds of agents over days" from a plain
`delegate_task` call. That is the kanban path or nothing.

## Workflow recipe (foreground)

1. **Decompose into independent units.** What is the unit — a file? an endpoint?
   a source? a record? Each unit must be answerable WITHOUT the others' output
   (else it's serial, not fan-out — see when_not_to_use).
2. **Deterministic pre-pass (Layer A).** In one `execute_code` script, gather the
   manifest: list the files, extract the candidate sites, fetch the raw sources,
   compute anything regex/parse can compute. Write a manifest to
   `/tmp/wf_<name>/manifest.jsonl` (one unit per line). This is the "plan in
   code." Print a count and stop.
3. **Size the fan-out** against `delegate-task-output-patterns`: chunk so each
   child handles ~8-12 mechanical file edits OR ~2000-3000 lines of reading OR
   ~50-70KB of corpus. Look at the LARGEST unit, not the average.
4. **LLM-judgment fan-out (Layer B).** Issue ONE `delegate_task` with a `tasks=[]`
   array, one task per chunk. Each task: reads its slice from the manifest,
   emits delimiter-separated lines to `/tmp/wf_<name>/out_<i>.csv`, prints a
   status word, stops. Do NOT depend on the `summary` field for content.
5. **Synthesize on the parent.** Read the out_*.csv files yourself, merge,
   present. The cross-cutting "whole picture" step stays on the parent — only the
   per-unit work fanned out.

## The novel mechanic worth building: adversarial convergence

This is the part Hermes did NOT already have and the real reason to bother.
Claude Code's quality claim ("independent agents try to refute each other's
findings; only surviving claims surface; iterate until they converge") maps
cleanly onto `delegate_task` batch mode:

### Recipe: N independent attempts + M refuters

For a finding-quality task (security audit, "is this code path actually
vulnerable?", "does this migration preserve behavior?", a high-stakes plan):

1. **Independent attempts (round 1).** Fan out the SAME question to N children
   (N=2-4) with DIFFERENT framings/angles in each `context`, so they don't
   collapse to the same reasoning. Each writes its claims to
   `/tmp/wf_<name>/attempt_<i>.md` as a list of discrete, individually-checkable
   claims (one claim per line — atomicity is what makes refutation possible).
2. **Collect + dedupe (parent or Layer A).** Merge all claims into a single
   numbered list. Identical claims from independent attempts = higher prior;
   note the agreement count per claim.
3. **Refutation round (round 2) — with burden of proof.** Fan out a refuter batch.
   Give each refuter the FULL file/source for each claim, not just the claim line —
   a refuter judging an out-of-context snippet cannot see the guard and cannot
   honestly break it. Set the bar in BOTH directions: to KILL a claim it must point
   to the specific guard that defeats it (name the auth check / validation / test /
   boundary and where it sits in the path); to KEEP a claim it must do the positive
   work — name the attacker, trace source → sink, and show no guard exists on that
   path and a trust boundary is actually crossed. Output
   `claim_idx|survives|guard_or_sink_evidence`.
4. **Keep only survivors — false until proven, not true until refuted.** A claim
   surfaces only if a refuter did that positive work; a claim that survived merely
   because nobody bothered to break it does NOT survive — under uncertainty, default
   to refuted and drop it (with a one-line reason if the user asked for completeness).
   This matters because a weak finder + a weak refuter is a false-positive machine —
   cheap skeptics rubber-stamp claims, so "no refuter broke it" defaults a claim to
   TRUE, which is the dominant failure mode. The burden-of-proof framing is what turns
   "survived refutation" from a rubber stamp into a real gate.
5. **Converge (optional).** If round 2 surfaced NEW claims (refuters often find
   adjacent issues), feed them back through one more refutation round. Stop when
   a round produces no new surviving claims — that's convergence. Cap at 3 rounds
   to bound cost.

This gives you the "more trustworthy than a single pass" property without a
runtime — it's just two `delegate_task` batches and a merge, structured so
disagreement is visible and unsupported claims die before they reach the user.

### Execution beats refutation when a claim is testable
Refutation is asymmetric: it can only DROP claims, and a confident refuter will
OVER-KILL — it marks a REAL bug `false_positive` on threat-model grounds ("that
host-check substring is fine", "that null byte can't reach the sink") when the bug
is in fact reachable. A refute-only pipeline has no way to overrule a wrong
refutation. So add one ground-truth gate: for any claim a small script can actually
exercise, fan out a cheap child to write the MINIMAL repro, RUN it (Layer A,
`terminal`), and treat the exit code as authoritative — a passing repro RESURRECTS a
claim the refuters killed; a repro that can't be made to fire confirms the drop. Net
rule: surface a claim if it survived refutation OR an execution repro confirms it.
Only reach for this on executable claims — skip it for inherently non-executable
ones (design, style, "this is fragile").

### Why atomic claims matter
A refuter cannot break "the auth layer has problems." It CAN break "endpoint
`POST /api/users/:id/role` in src/routes/users.ts:142 has no role check." Force
attempts to emit specific, located, individually-falsifiable claims or the
refutation round is theater.

## Cost discipline (this is the thing that bites)

A workflow can consume dramatically more tokens than a normal turn — that is
inherent, not a bug. Two real multipliers:

- **Each Layer-B child is a full agent tree.** 20 children ≈ 20× the model calls.
  `delegation.max_concurrent_children` only bounds *concurrency*, not *total*.
- **Hermes aux/subagent model defaults to main-model-first.** Children inherit
  the parent's (often expensive reasoning) model unless you pin a cheaper one.
  For mechanical fan-out, pass a cheaper model per task if the config supports it,
  or do the deterministic part in Layer A (no per-item LLM at all).

Always: start on a SCOPED slice (one directory, 20 records, 10 endpoints), prove
the recipe end-to-end, report the token cost, THEN offer to run it at full scale.
Never silently fan out hundreds of children — surface the cost first and let the
user say go.

## Pitfalls

- **Writing `delegate_task` inside an `execute_code` script.** It's not in
  `SANDBOX_ALLOWED_TOOLS`; the import/stub won't exist. Layer A is deterministic
  tools only. Fan out LLM judgment from the parent turn, not from inside a script.
- **Promising background/resumable from `delegate_task`.** It's synchronous and
  turn-scoped. Durable = kanban swarm.
- **Trusting `summary` fields for content.** Route structured output to files
  (Pattern 2 in delegate-task-output-patterns).
- **Empty children silently capping recall.** A child can also return *nothing* — it
  burned its whole token budget thinking and stopped at the limit, so its chunk drops
  from the union with NO error and recall is quietly capped (a 25-unit sweep that
  loses ~11 empty units recalls about half what it should). This is the OPPOSITE of
  the "stalled child wrote anyway" case — here there is genuinely no file. Fix is
  cheap and idempotent: detect the holes (a missing or zero-length `out_<i>`) and
  RE-DISPATCH ONLY THOSE units, not the whole batch.
- **Letting a confident refuter kill a testable bug.** A refuter will mark a real,
  reachable bug a false positive on threat-model grounds. If a small script can
  exercise the claim, run the repro — execution overrules refutation.
- **Non-atomic claims in the verify recipe.** Unfalsifiable claims survive
  refutation by default and pollute the output. Force located, specific claims.
- **Same framing in all "independent" attempts.** They collapse to one answer and
  the cross-check is worthless. Vary the angle in each child's context.
- **Fanning out a serial task.** If unit B needs unit A's output, parallelism
  produces wrong/empty results. Re-check independence before fanning out.

## Verification before you call it done

- Did the deterministic pre-pass actually run, and does the manifest line-count
  match the expected unit count? (`wc -l /tmp/wf_<name>/manifest.jsonl`)
- Did every fan-out child write its output file? (`ls /tmp/wf_<name>/out_*.csv`) —
  remember stalled children often completed anyway (Pattern 6), but a child that hit
  its token limit returns EMPTY: re-dispatch only the missing/zero-length holes.
- For the verify recipe: can you point to the guard/sink evidence for every DROPPED
  claim, confirm every SURFACED claim met the burden of proof (not just "unrefuted"),
  and run a repro for every surfaced claim that is testable?
- Did you report token cost on the scoped run before offering full scale?
