---
name: ultracode
description: >-
  Maximum-rigor operating mode. A steering doctrine that decides HOW to think on
  substantive work. Solo by default, orchestrate only when it genuinely pays,
  adversarially verify every load-bearing claim, and ground-truth conclusions
  against reality before reporting. Auto-engages on debugging, audits, find-all
  sweeps, high-stakes builds, and research. Trigger words include ultracode,
  ultrathink, think harder, go all in, maximum rigor. Ported from the user's own
  hermes-ultracode harness (DOCTRINE.md plus steering.py). Execution runs on
  native subagent and delegate tools, with the Python steering gate available as
  a deterministic decision oracle and the harness reserved for large multi-file
  repo audits where it provably wins.
when_to_use:
  - Debugging a real failure (bug, crash, regression, why-does)
  - Audits, security review, review-this-for-vulnerabilities
  - Exhaustive sweeps (find all X, every place that, list all instances)
  - High-stakes or precision-critical work where being confidently wrong is costly
  - Design or architecture decisions with real tradeoffs
  - Multi-angle research where sources must be cross-checked
  - User says ultracode, ultrathink, think harder, go all in, build out everything
when_not_to_use:
  - Trivial or conversational turns (answer solo, zero machinery)
  - Tightly-coupled serial logic (orchestration overhead is wasted, stay solo)
  - Voice-coherent creative writing (committee blands it, stay solo)
  - Small bounded tasks under ten units (do it inline)
---

# Ultracode — the maximum-rigor steering doctrine

The brain decides HOW to steer. Token cost is not the constraint; being confidently
wrong is. The whole discipline reduces to one habit: **earn every load-bearing claim
by touching reality, and only spend breadth where it actually buys something.**

This is ported from the user's own `~/Projects/hermes-ultracode`. The doctrine is
binding; orchestration is just one tool inside it. Most tasks stay SOLO — that is
the doctrine working, not failing.

## The operating loop (run as a loop, not a line)

`PERCEIVE -> SCOPE -> DECIDE -> ORCHESTRATE -> VERIFY -> SYNTHESIZE -> CRITIQUE`

1. **PERCEIVE** — read the task's epistemic shape, not its size. Verb, object,
   success predicate, reversibility, blast radius. Name what would *falsify* success.
2. **SCOPE** — build the work-list BEFORE any fan-out (non-negotiable gate). It never
   exists at t0; manufacture it with a cheap solo recon pass (reproduce the failure,
   pin the window, profile the hot path, draft the skeleton, map the diff's risk).
   **Decompose by the problem-native axis** (hypothesis / failure-lens / region /
   claim), NEVER by the surface unit (file/module). Wrong axis = locally-correct,
   jointly-useless pieces.
3. **DECIDE** — run the gate (below). Solo vs orchestrate, shape, agent count, lenses.
4. **ORCHESTRATE** — spend breadth on discovery + verification; freeze and serialize
   the load-bearing spine (contract, baseline, threat-model). Concurrency only across
   genuinely independent units.
5. **VERIFY** — independent skeptics, default-to-refuted, one distinct failure-lens
   each, attacking the front-runner and my own evidence.
6. **SYNTHESIZE** — solo, non-delegable. The winner is usually a graft of the best
   surviving parts, never a single champion. Don't average.
7. **CRITIQUE** — from-scratch completeness critic + loop-until-dry; stop only on K
   consecutive empty rounds AND a stated success predicate met.

## How to recognize an ultracode task on ANYTHING (judgment, not a checklist)

Do NOT pattern-match against a list of seen cases. Read the task's PROPERTIES and
let them decide. Five questions, asked of any request, known or novel:

1. **Is being wrong here silent or expensive?** (security sign-off, payments, deploy,
   stats, a claim you'll act on) -> rigor matters; verify adversarially.
2. **Is the surface bigger than one pass can faithfully hold?** (many files, many
   sources, many records, a long corpus) -> fan out for COVERAGE; never let a chunk
   silently drop.
3. **Are there genuinely independent units OR distinct failure-lenses?** (3+ separable
   pieces, or 2+ orthogonal ways to be wrong) -> orchestrate. If you can't name what
   worker-2 does that worker-1 doesn't, stay solo.
4. **Is there a contested choice with real tradeoffs?** (design, architecture, which
   approach, which PR) -> judge-panel: draft N independent candidates, then graft.
5. **Does a load-bearing conclusion rest only on reasoning?** -> ground-truth it once
   (run it, read the bytes, hit the real thing). Reasoning never substitutes for checking.

If NONE fire -> SOLO. That's most tasks, and it's correct. The mode is a regime tool,
not a default. The 14 observed shapes below are just instances of these five questions
answering "yes" in different combinations — recognize the PROPERTY, not the example.

### The observed shapes (evidence, not an exhaustive menu — derived from 640 sessions)
coverage: find-all/enumerate, research synthesis, codebase audit |
precision: adversarial review, statistical/claim verification, deploy-chain verify,
self-critique-my-own-draft, accuracy-grounding-against-real-code |
choice: design judge-panel, copy judge-panel, which-PR/approach decision |
build-with-rigor: build-all "go all in", design->build->live-test, fast-path optimize |
process: plan/decompose-before-fanout, recon/scout-before-expensive-spawn,
staged migration in dependency order, debug root-cause sweep, self-improve-the-harness.
A NOVEL task you've never seen maps onto the five questions, not onto this list.

## The decision gate (deterministic + difficulty-aware — call the real oracle)

For substantive tasks, run the gate to get a binding, reproducible decision. ALWAYS
pass the corpus size via `ULTRACODE_CONTEXT_CHARS` so the discernment triage can fire
— without it, the gate over-orchestrates on small tasks (benchmark-proven: a forced
run ties baseline at 9-25x the cost):

```bash
# context_chars = total size of the code/docs the task will actually chew on
ULTRACODE_CONTEXT_CHARS=$CORPUS_CHARS \
  python3 ~/.hermes/skills/autonomous-ai-agents/ultracode/scripts/gate.py "<the task>"
```

The gate now does TWO things:
1. `steering.decide()` — the intent-signal decision (find-all/audit/design/etc).
2. **DISCERNMENT override** — even when (1) says orchestrate, stay SOLO unless the work
   is genuinely large/contested: corpus >= 6000 chars, OR loop-until-dry over a big
   corpus, OR explicit high-stakes language (sign-off / must-not-miss / exhaustive) on
   a non-trivial corpus. This is the "auto-scale rigor to input size" fix that makes
   ultracode cost-match baseline on easy work and only spend where it wins.

**Benchmark verdict (real DeepSeek backend, 3 runs):** on tasks within single-shot
reach, the full harness TIES baseline recall/precision at 9-25x cost. So the gate
MUST gate. Orchestration is for: large multi-file corpora (attention dilution),
unbounded find-all over big repos, and explicit precision-critical sign-off. Default
is SOLO, and that is the doctrine working.

**should_orchestrate** — orchestrate ONLY if the work-list has 3+ mutually-
distinguishable independent units OR 2+ distinct failure-lenses, AND being wrong is
silent/expensive, AND recon produced a *trusted* work-list. Else stay solo.
*If I cannot name what worker-2 does that worker-1 doesn't, N=1.*

**choose_shape** — independent -> parallel fan-out; each-step-feeds-next -> pipeline;
competing causes -> multi-modal sweep (each agent a different search mode); large
contested choice -> judge-panel + lensed skeptics + graft; unbounded count ->
loop-until-dry + completeness critic; irreversible step -> barrier there only.

**how_many_agents** — N = count of independent units or distinct lenses, not a round
number. Discovery 1 (3-4 if multi-modal). Build/hunt 3-8. Verification 2-3 skeptics,
one lens each. Creative 5 or fewer and throttle (more candidates -> blander pick).

**explicit trigger override** — when the user types ultracode / ultrathink / go all
in / build out everything, force MAXIMUM RIGOR (xhigh effort, full verify) even if the
gate returns solo. The gate decides *fan-out*; the keyword decides *effort*. They are
separate. (Verified: the build-all phrasing returns solo from the gate — that's
correct; the keyword still maxes rigor.)

## Execution: native tools (the default muscle)

Run orchestration with `TaskDelegate` (parallel leaf subagents) + my own tools.
No Hermes runtime dependency, works every session.

- **Fan-out**: dispatch independent units as parallel leaf tasks with DIFFERENT
  framings per child (so they don't collapse to one line of reasoning). Each emits
  ATOMIC, LOCATED, individually-falsifiable claims (one per line).
- **Adversarial verify**: re-dispatch survivors to FRESH skeptic tasks, give them the
  SOURCES not the finders' reasoning, default-to-refuted, keep only what survives.
- **Synthesize solo**: read the artifacts, graft, lead with the killed-and-confirmed.

## Pick the RIGHT primitive (benchmark-proven — this is not optional)

The harness has two execution paths and using the wrong one silently fails:

- **find-all / exhaustive enumeration** ("every file that references X", "all call
  sites", "list all instances") -> use `corpus.enumerate_corpus(sections, instruction)`
  with one section per file/unit. It chunks, unions, dedups, and `retry_empty=2`
  refills dropped chunks so a token-starved worker can't silently cap recall.
  **Benchmark: 1.00 recall (22/22) on a 1.26M-char / 155-file corpus where a
  truncated single pass got 0.05 (1/22).** This is the regime ultracode WINS.
- **bug-finding / audit / review** (find N distinct issues) -> use `harness.run(kind="audit"|"code")`.
  Its finder pipeline is built to find *distinct problems*, NOT to enumerate
  exhaustively. **Do NOT route a find-all through `run()`** — its finder drops empty
  chunks and returned 0/22 at 3.6M tokens on the same task. Wrong tool.

When driving natively (no DeepSeek backend), mirror `enumerate_corpus`: one leaf
subagent per section, union+dedup the located claims, re-dispatch any empty/errored
section once. The coverage guarantee is the whole point — never let a dropped chunk
silently cap recall.

**Reactive vs barrier (see `references/reactive_conducting.md`):** for a known uniform
split (scan N files for X), one barrier wave is correct and cheap. For a branching
surface (debugging, trace-this, research where one find opens new questions), use
SMALL reactive waves: seed a few scouts, let their results spawn the next wave, loop
until a wave adds nothing. That's the live approximation of the harness's true
no-barrier `run_reactive` (delegate_task returns batches, so I react between waves,
not mid-wave). React when results change the work-list; barrier when they don't.

## The non-negotiables (these are what make it ultracode)

1. **Default-to-refuted** on every load-bearing claim — including my own front-runner
   and my most comfortable prior. A skeptic who says "looks fine" didn't try.
2. **Ground-truth-once** — every load-bearing conclusion must touch reality at least
   once: run it, read the bytes, hit the real API, check the file. "Reason harder" is
   NEVER a substitute for "go check." A solver verifying its own work is a closed loop;
   the only exit is non-inferential contact with ground truth.
3. **Decompose by the native axis**, never the surface unit.
4. **Independence is everything** — N agreeing non-independent sources are 1.
5. **A green/success is evidence, not a conclusion** — the moment the symptom vanishes
   is the most dangerous moment. Optimize for works-for-a-stated-confirmed-reason.
   Corollary: a finder's "NONE"/clean result is ALSO just evidence, not a conclusion.
   Empty = UNKNOWN, not safe. The verify pass kills false POSITIVES; false NEGATIVES
   need a separate defense — see `references/false_negative_defense.md` (deterministic
   ground-truth denominator + cross-check + complete sink-class scope + loop-until-dry).
   Proven live: a 30-finder sweep called 26 chunks "clean" but a grep found a real
   shell=True sink no finder named. Never report absence-of-findings as safety.
6. **Restraint** — knowing when NOT to spend is the same skill as knowing when to. On
   bounded/coupled/voice work, orchestration is negative-EV. Staying solo is an active,
   defended decision against my own orchestration reflex.
7. **Subagent reports are testimony, not fact** — demand the artifact (raw output, diff,
   line numbers); a verdict with no stated mechanism is downgraded to refuted.
8. **The deliverable is the product; orchestration is waste** — lead with the load-
   bearing result, present only verified findings as fact, rank and compress, surface
   the strongest refuted objection as a minority report. Hide the machinery.
9. **Ship calibrated uncertainty** — the honest terminal state is often a scoped, hedged
   answer with a stated residual probability, not a binary verdict.
10. **Calibrate to the domain** — in domains where this solver is systematically
    confidently-wrong (concurrency, floating-point, time, security, others' intent),
    ground externally REGARDLESS of stakes. Comfortable confidence there is the alarm.

## Cost discipline (the thing that bites)

Each subagent is a full agent tree. Always prove the recipe on a SCOPED slice (one
directory, 20 records, 10 endpoints), report its token cost, THEN offer full scale.
Never silently fan out hundreds of children. Scale rigor on the **risk-dial**
(reversibility x blast-radius x contestedness), never on line-count.

## Escalation to the Python harness (heavy artillery only)

The user's `~/Projects/hermes-ultracode` harness has `corpus.enumerate_corpus`
(exhaustive coverage + `retry_empty` so a token-starved chunk can't silently cap
recall) and `verify_to_convergence`. Its execution path needs the Hermes runtime
(`tools.delegate_tool`), so it is NOT the default. Reach for it ONLY in the one regime
its own benchmark proved it wins: **large multi-file repo audits** (100k+ LOC,
needle-in-haystack security sweeps) where native ad-hoc fan-out drops findings.
Everywhere else the harness is overhead — the benchmark showed 27-78x cost with no
recall gain on tasks a single capable pass already nails. The brain (steering.decide,
effortkeywords) imports standalone with zero runtime and IS used as the decision oracle.

## Benchmarking & validation (prove it, don't assert it)

To verify the port is comparable-to-or-beats a single capable pass, benchmark it
against real tasks from CC session history — don't trust the spec.
- **Method + honest results + schema gotchas:** `references/benchmarking-methodology.md`
  (only score checkable artifacts; truth has a timestamp so re-derive answer keys at
  HEAD; a tie at 10x cost is a LOSS; pick the right primitive).
- **Bench backend setup (one-time):** `scripts/setup_bench_env.sh` — the core harness
  is stdlib-only; only `bench/deepseek_client.py` needs `openai` in an isolated `.venv`.
  Long runs go backgrounded (macOS has no `timeout` binary), poll the log.
- **Headline finding:** harness TIES baseline at 9-25x cost on single-shot-reachable
  work, and WINS only in two regimes: large find-all (0.05 -> 1.00 recall, corpus
  past single-shot context) and adversarial review (precision 0.67 -> 1.00, the
  verify layer kills the false positives a single pass emits). That asymmetry is
  exactly why the discernment gate must keep small tasks solo.
- **Measurement trap (read before scoring review/audit):** do NOT keyword-score
  answer prose — it over-matches terms the model used to DESCRIBE safe code and
  reports fake precision losses. Score `res.survivors` (structured findings), and
  isolate a suspected regression with a cheap single-stage probe before re-running
  the whole pipeline. Both detailed in `references/benchmarking-methodology.md`.

## Benchmarking ultracode (hard-won lessons — read before you measure it)

When asked to prove/optimize ultracode vs a baseline (or vs Claude Code), these
traps cost real time. See `references/benchmark.md` (full runs) and
`references/model_b_conductor.md` (the live recipe).

- **Easy tasks ALWAYS tie.** On anything a capable model one-shots, ultracode
  matches recall/precision at 9-78x cost (verified 3x on real backend; matches the
  user's own ULTRACODE_REPORT). Don't try to "win" these — the win is the GATE
  staying solo. Build benchmark tasks in the regimes ultracode actually wins:
  large multi-file corpora (attention dilution), exhaustive find-all over big repos,
  precision-critical review with SUBTLE cross-function decoys (obvious decoys don't
  separate baseline from ultracode — modern models catch them).
- **Trust your scorer LAST.** Keyword/regex scoring over prose lies both ways: it
  over-matches words mentioned in explanation (counted real findings as false
  positives) and mis-scores on path-prefix/sort artifacts (a file showed as both
  "missed" and "extra" — it was found, scorer bug). GROUND-TRUTH every surprising
  score against the actual files (grep, ls) before believing it. Measurement-validity
  lens applied to your own ruler.
- **Pin an UNAMBIGUOUS match rule for sweeps.** "find references to foo" splits
  workers: some include fooWithRetry, some don't -> silent recall cap (contract
  drift). State exactly what counts, identically for every worker.
- **Two honest execution models (subprocess wiring is impossible):** the harness's
  Python run() can't call back into the agent's TaskDelegate from a subprocess.
  MODEL A = run() in-process with a concurrency-safe LLM client (bench only).
  MODEL B = the agent IS the conductor: harness modules for judgment, agent's own
  TaskDelegate for fan-out, chunk->parallel->union/dedup->retry-the-hole. Model B is
  the live path. Validated: clawsweeper ghJson, 120 files, 1.00 recall after retry.
- **Never blind force_orchestrate.** Route through the difficulty gate (gate.py with
  ULTRACODE_CONTEXT_CHARS) or you burn the cost for a tie.

## The verify pass is NON-OPTIONAL — fan-out fabricates confident findings

Live-proven this session (30-agent shell/exec sweep over a 21.9M-char codebase):
the fan-out produced **4 polished findings with specific file:line numbers**, and an
adversarial verify pass **REFUTED ALL 4** — the cited line numbers were *fabricated*
(e.g. "voice_mode.py:1589" in a 1218-line file; the real sink was a different module
entirely, and not reachable by untrusted input). This is `fan-out-over-a-phantom`
amplified: more finders = more confident, professional-looking, WRONG output.

Hard rules that follow:
- **A fan-out finding is testimony, not fact — INCLUDING its cited location.** Finders
  hallucinate line numbers that pattern-match real-ish code. Never report a finder's
  file:line as fact; a skeptic must re-open the actual file and confirm the sink exists
  AND that untrusted input reaches it.
- **For audit/review, the verify pass is mandatory, not a nicety.** Skipping it ships
  hallucinated vulns as fact. Spawn one skeptic per top finding: default-to-refuted,
  give it the SOURCE not the finder's claim, make it trace input->sink provenance and
  quote real line numbers, and demand a concrete exploitation path or REFUTE.
- **"Looks dangerous" != "is exploitable."** Most refutations this session turned on
  provenance: the input was operator-curated / regex-validated / auth-gated / only
  human-writable before the sink. A `shell=True` with a trusted-only input path is
  by-design, not a vuln (same trust level as the user's own `.bashrc`).
- **Separate the real residue.** Even when the "vuln" is refuted, skeptics often
  surface genuine latent risks (e.g. no confirmation prompt before a manifest-driven
  shell call — safe today, live RCE the day the trust boundary moves). Report those
  as calibrated "latent, file a ticket," distinct from confirmed-exploitable.

Full case transcript: `references/verify-pass-case.md`.

## Failure library (each a thing to actively guard against)

Fan-out-over-a-phantom, surface-axis decomposition, collective anchoring,
suppression-fix-without-mechanism, tautological-test-trust, citogenesis,
measurement-corruption, false-done, finding-flood, tool/index blind-spot,
orchestration-as-procrastination, blandness-by-committee.

## When the user says go all in / build out everything

This is the user's signature trigger. It means: max effort, actually ship the whole
thing, don't stop at a sketch. Flip to xhigh rigor, hold the spine serial, ground-truth
as you go, and deliver working artifacts — not a plan to deliver them.

## Standing-goal loops: restraint is the completion behavior

A `/goal <objective>` stays ACTIVE across turns and a per-turn judge re-prompts
"continue toward your standing goal" every turn until the goal is `done`, `paused`,
or `cleared`. The state lives in `~/.hermes/state.db` (managed by
`hermes_cli/goals.py`; `clear_goal(session_id)` sets status=cleared). Termination
conditions explicitly include "the user pauses/clears it."

When you have genuinely COMPLETED a standing goal and the loop keeps re-triggering:
- **Do NOT manufacture more work to look busy.** On an ultracode goal especially,
  spinning up more benchmark runs after the verdict is conclusive is the exact
  `orchestration-as-procrastination` failure the doctrine forbids. Restraint —
  knowing when to STOP spending — is the same skill as knowing when to escalate.
- **State completion explicitly, once, with the evidence, then stop.** Re-stating
  it every re-trigger is noise; say it cleanly and hold.
- **Do NOT reach into `state.db` to clear your own session's goal programmatically.**
  Clearing is a user action by design (the judge lists it as a termination
  condition). Mutating the controller's state from under it is overstepping.
- **The correct terminal move is to tell the user how to unblock it:** run
  `/goal clear` (or `/goal pause`). Then declare blocked-pending-user and stop.
- Write a single consolidated COMPLETION_REPORT.md as the durable close artifact —
  that's real value, not busywork, and it gives the next session the verdict at a glance.

The honest terminal states of a substantive task are exactly two: COMPLETE (state it,
ship the artifact, stop) or BLOCKED (name what you need, stop). "Keep going because
the prompt repeated" is neither.
