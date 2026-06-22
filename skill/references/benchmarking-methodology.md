# How to benchmark the ultracode port (vs single-pass baseline / CC)

The reusable method for proving the harness is "comparable or beats" a single
capable pass. Built and validated this session against the real DeepSeek backend.

## Core principle: only score CHECKABLE artifacts
A task is benchmarkable only if it leaves a ground-truthable result:
- find-all sweep  -> a SET (files/symbols) you can re-derive with grep at HEAD
- adversarial review/audit -> a finding set with planted reals + decoys
- design judge-panel -> a stated winner + reasons
Build-coupled tasks ("clear the backlog", "build the economy") are NOT scorable —
the repo moved and "did I build the same thing" has no clean metric. Skip them.

## Truth has a timestamp (the trap that bit us)
CC's session enumerations are stale — the repo evolves, line numbers drift, files
move. NEVER score line-for-line against a CC transcript. Re-derive the answer key
against the CURRENT HEAD (a fresh grep), then score on the current ground truth.

## Metrics
- recall    = found / should-find
- precision = real / all-claimed   (decoys flagged as real = false positives)
- decision-match = did the gate pick the same solo-vs-orchestrate + shape as CC
- cost = total tokens (the whole point — a tie at 10x cost is a LOSS)

## The A/B harness shape (see scripts/run_benchmark.py for a copyable runner)
For each task, run BOTH and compare:
1. BASELINE: one `client.chat([...])` with the task + corpus. For large corpora,
   truncate to a realistic single-shot window (~120k chars) — that truncation IS
   the baseline's real-world limit and is the source of its recall ceiling.
2. ULTRACODE: the matching primitive (see "right primitive" below), same backend.
Score both, print `recall/precision/cost`, declare WIN only if quality holds AND
either recall rises or cost drops materially.

## Pick the right primitive (the bug that cost 3.6M tokens for 0/22)
- find-all / exhaustive enumeration -> `corpus.enumerate_corpus(sections, instr,
  retry_empty=2)`, ONE section per file. Coverage-guaranteed. Got 22/22.
- bug-finding / audit (find N distinct issues) -> `harness.run(kind="audit")`.
  Do NOT route a find-all through `run()` — its finder drops empty chunks silently
  and returned 0/22 at 3.6M tokens on the same corpus.

## Findings reproduced this session (the honest verdict)
| task | corpus | baseline | ultracode | verdict |
|---|---|---|---|---|
| AXProbe find-all | 67k (9 files) | recall 1.00, 18k tok | 1.00, 163k tok | TIE, 9x cost |
| precision audit | 2k | R1.00 P1.00, 3.4k tok | 1.00/1.00, 85k tok | TIE, 25x cost |
| large find-all | 1.26M (155 files) | recall 0.05, 27k tok | 1.00, 1.9M tok | WIN |
| adversarial review (subtle cross-fn decoys) | 2k | R0.67 P0.67, 1 FP | R0.67 P1.00, 0 FP | WIN (precision) |

Lesson: on single-shot-reachable work the harness TIES at 9-25x cost — so the
DISCERNMENT gate (gate.py difficulty override) MUST keep those solo. The harness
only earns its cost in the attention-dilution regime (corpus past single-shot
context), where it goes 0.05 -> 1.00, AND in adversarial review where the verify
layer kills the false positives a single pass emits (precision 0.67 -> 1.00).

## DON'T keyword-score review/audit quality — score the structured survivors
The biggest measurement trap of the session. The review benchmark's regex scorer
matched decoy words ("discount", "current_user") in the answer's PROSE — where the
model was *describing safe code or tracing data flow*, not flagging a bug — and
counted them as false positives. That reported a fake precision LOSS (P=0.60) when
the verify layer had actually refuted every decoy (proven by an isolated
`verify_findings` run: 0/2 decoys survived, default AND context-aware skeptic).

Rules so this doesn't bite again:
- A decoy counts as a false positive ONLY if it is ASSERTED as a bug — require the
  decoy term to co-occur with bug/vuln/flaw/exploit language, not appear anywhere.
- Better: score on `res.survivors` (the structured findings with verdicts), NOT
  regex over the synthesized prose. The harness exposes survivors for exactly this.
- This is the doctrine's own `measurement-corruption` / `measurement-validity`
  lens turned on your own benchmark: a bent ruler reports a fake regression. When a
  result looks like a loss, validate the SCORER before patching the harness.

## Isolate before you spend (the cheap-probe pattern)
When a full A/B run (80-160k tok) shows a suspected regression, DON'T re-run the
whole pipeline to test a fix hypothesis. Feed just the suspect findings + corpus to
the single stage in question (e.g. `verify_findings` with directive A vs B) for a
few k tokens. That isolated probe is what revealed the scorer — not the skeptic —
was the leak. Ground-truth the component, not the whole machine.

## Skeptic directive is injectable (verify-stage tuning seam)
`verify_findings(..., skeptic_directive="...")` and the planner's
`approach.skeptic_directive` let you strengthen refutation WITHOUT editing the
harness repo. A caller-context-aware directive ("is this exploitable GIVEN how its
callers use it? trace data flow from every caller; refute if clamped/guarded/
non-security in context") is the lever for context-safe decoys — though this
session's decoys were already killed by the default skeptic, so reach for it only
when isolated probing shows the default skeptic actually letting FPs through.

## Schema gotchas (verified against the repo, not guessed)
- `Finding(claim=..., locator=...)` — it's `locator`, NOT `location`.
- `run()` kwargs: task positional, then context/kind/delegate_fn/aux_call_fn/
  config/force_orchestrate/run_id/enable_ledger (keyword-only after task).
- `dedupe_findings` increments `agreement_count` on convergent duplicates.
