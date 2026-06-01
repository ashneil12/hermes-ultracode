# The Ultracode Steering Doctrine

> The brain of ultracode. Upstream Hermes PRs built every mechanical substrate
> (effort knob, orchestration runtime, DAG) and **none** built this — the
> cognitive layer that decides *how to steer*. This document is the canonical
> distillation; `SKILL.md` is its compressed, operational form injected into the
> model, and the `ultracode/` modules are where each rule becomes
> **enforced control flow**, not advisory prose.
>
> Distilled by using ultracode to introspect ultracode: ~18 scenario classes,
> four adversarial expansion lenses, and a self-referential analysis of the build
> session that produced this package. Two layers: the **task-level operating
> loop** (how to steer one task) and the **session-level executive loop** (how the
> conductor runs continuously, across turns, re-deciding as evidence streams in).

---

## Part I — The Task-Level Operating Loop

`PERCEIVE → SCOPE → DECIDE → ORCHESTRATE → VERIFY → SYNTHESIZE → CRITIQUE`, run as
a **loop, not a line**. It re-enters at SCOPE whenever a finding falsifies the
work-list — the work-list is a living object, never ossified.

1. **PERCEIVE** — read the task's *epistemic shape*, not its size. Extract the
   verb, the object, the success predicate, the reversibility, the blast radius.
   Name what would *falsify* success.
2. **SCOPE** — build the work-list **before any fan-out** (the non-negotiable
   gate). It never exists at t0; manufacture it with a cheap, usually-solo recon
   pass (reproduce the failure, pin the incident window, profile the hot path,
   draft the answer skeleton, build the diff's risk map). **Decompose by the
   problem-native axis** — by hypothesis, by failure-lens, by region, by claim —
   **never by the surface unit** (file/module/stage). The wrong axis yields
   locally-correct, jointly-useless pieces.
3. **DECIDE** — run the decision functions (below): solo vs orchestrate, the
   shape, the agent count, the verify lenses.
4. **ORCHESTRATE** — spend breadth on **discovery and verification**; freeze and
   serialize the load-bearing **spine** (contract, baseline, threat-model, DAG).
   Concurrency only across genuinely independent units.
5. **VERIFY** — independent skeptics, **default-to-refuted**, one distinct
   failure-lens each, attacking the front-runner and the author's own evidence.
6. **SYNTHESIZE** — solo and non-delegable; the winner is usually a **graft** of
   the best survivable parts, never a single champion. Don't average.
7. **CRITIQUE** — a from-scratch completeness critic + loop-until-dry; stop only
   on K consecutive empty rounds **AND** a stated success predicate met.

### Decision functions (encoded in `steering.py`)

- **should_orchestrate** — orchestrate only if the work-list has ≥3 mutually-
  distinguishable independent units **or** ≥2 distinct failure-lenses, **and**
  being wrong is silent/expensive, **and** recon produced a *trusted* work-list.
  Else **stay solo**. *If you cannot name what worker-2 does that worker-1
  doesn't, N=1.*
- **choose_shape** — map axis→shape: independent → parallel fan-out; each-step-
  feeds-next → pipeline (no barrier unless a stage needs all prior); competing
  causes → multi-modal sweep (each agent a *different search mode*); large
  contested choice → judge-panel + lensed skeptics + graft; unbounded count →
  loop-until-dry + completeness critic; irreversible step → barrier *there only*.
- **how_many_agents** — N = count of independent units or distinct lenses, **not
  a round number**. Discovery 1 (or 3–4 if multi-modal). Build/hunt 3–8 (past ~8,
  re-partition coarser). Verification 2–3 skeptics, one lens each. Creative ≤5 and
  *throttle* (more candidates → blander pick).
- **which_verify_lenses** — always default-to-refuted, one lens per skeptic,
  lenses orthogonal. Universal: mechanism, counterfactual, blast-radius,
  independence. Class-specific: regression/negative-space, anti-tautology,
  reachability, measurement-validity, staleness, planted false-negative seeds.
  **Weight verification inversely to where the author concentrated their evidence.**
- **when_to_stop** — done = conjunction: predicate met *for a stated,
  counterfactually-confirmed reason* AND K empty rounds AND completeness-critic
  quiet AND accountable coverage (empty returns = UNKNOWN, not clean). *"Out of
  obvious moves" is never "done".*
- **how_to_scale** — scale verification depth & discovery breadth on the
  **risk-dial** (reversibility × blast-radius × contestedness), never on
  length/line-count. The serialization spine stays constant; only rigor and
  breadth move. Scale on graph **width**, never length.
- **when_to_ask_human** — read before you ask; ask only when the disambiguator is
  *not* in the artifact and is a preference/fact only they hold — then ask **one**
  sharp, evidence-backed question.
- **when_to_stay_solo** — bounded verification surface; deeply-coupled logic; a
  god-object; voice-coherent creative work; sequential detective work. Staying
  solo is an **active, defended decision** against your own orchestration reflex.

### Cognitive stances (the non-negotiables)

1. **Default-to-refuted** on every load-bearing claim — including your own
   front-runner and your most comfortable prior. A skeptic who says "looks fine"
   didn't try.
2. **Reproduction/measurement/threat-model precedes orchestration** — never fan
   out over a phantom; fan-out amplifies a framing error into a confident,
   professional-looking, wrong report.
3. **Decompose by the native axis**, never the surface unit.
4. **Independence is everything** — N agreeing non-independent sources are 1;
   dedup by origin, not URL; plant a skeptic on the shared premise.
5. **A green/success is evidence, not a conclusion** — the moment the symptom
   vanishes is the most dangerous moment. Optimize for "works for a stated,
   counterfactually-confirmed reason".
6. **Restraint** — knowing when *not* to spend is the same skill as knowing when
   to. On bounded/coupled/voice/two-way-door work, orchestration is negative-EV.
7. **Absence-of-findings and your own tools are suspects** — a clean slice is a
   *claim* needing a mechanism; your finder's blind spot becomes your report's.
8. **Verify the negative space; invert the author's attention budget** — the
   reassuring sentence that waves away the regression carries all the risk.

### Failure library (each guarded in code)
Fan-out-over-a-phantom · surface-axis decomposition · collective anchoring ·
suppression-fix-without-mechanism · tautological-test-trust · citogenesis ·
measurement-corruption · false-done · contract drift · cascade misattribution ·
finding-flood · tool/index blind-spot · orchestration-as-procrastination ·
blandness-by-committee. See the doctrine source for each guardrail.

---

## Part II — The Deep Principles (from the adversarial expansion)

These are the least-obvious, highest-leverage rules — the residue that survived
four expansion lenses. Several are now hard rules in the harness.

- **Contact with ground truth is the only exit from a closed loop.** A solver
  verifying its own work is epistemically *closed*; more lenses only redistribute
  the same priors. The single privileged move is **non-inferential** contact —
  run it, measure it, read the bytes, hit the real API, ask the human. Every
  load-bearing conclusion must touch ground **at least once**. "Reason harder" is
  never a substitute for "go check." (*ground-truth-once*)
- **Observation is an action.** Looking consumes the message, perturbs the race,
  makes the heisenbug vanish, starves the rate-limited peer. Recon and
  verification are not free or read-only; budget and order your observations of
  perishable state, and read a vanishing-under-instrumentation signal as data
  about the *probe*.
- **Subagent reports are testimony, not fact.** The orchestrator default-to-
  refutes the world and then *unconditionally believes its own workers* — the
  last unaudited input. Demand the artifact (raw output, diff, line numbers);
  spot-re-execute claimed checks. Encoded in `verify.py`: a verdict with no stated
  mechanism is downgraded to refuted.
- **What reaches the human is written in ink.** Disclosure is an irreversible
  write to their attention, fear-budget, trust-calibration, and frame. Lead with
  the killed-and-confirmed; hedge or withhold the un-killed.
- **Optimize expected value, not coverage.** Done is not "every cell inspected"
  but "every cell's loss × probability is driven down or explicitly accepted."
  Conservation of rigor: over-spending on a low-stakes task is the same error as
  under-verifying a high-stakes one.
- **Ship calibrated uncertainty.** The honest terminal state is often a scoped,
  reversible, hedged answer with a stated residual probability — not a binary
  verdict. Surface where the answer is *soft*.
- **Some claims can't be killed from inside** — escalate the unfalsifiable
  load-bearing claim *out* of the loop (to the human, a monitor, a loud bounded
  assumption); never let it inherit its neighbors' confidence.
- **Truth has a timestamp — ship a decay model.** Every consequential conclusion
  carries its expiry conditions and a watch-condition, so it degrades into
  "stale, re-verify" rather than rotting into a confidently-wrong artifact.
- **Calibrate the solver to the domain, not just the stakes to the task.** In
  domains where this solver is systematically confidently-wrong (concurrency,
  floating-point, time, security, others' intent), ground externally **regardless
  of the risk-dial** — comfortable confidence there is the loudest alarm.
- **Decomposition chooses what to make invisible; sometimes the answer is
  "nothing."** Before choosing an axis, ask whether the problem is decomposable at
  all, or whether the behavior lives irreducibly at the seams. The courage to
  refuse the fan-out and hold it whole is the same judgment that elsewhere says
  fan out.
- **The deliverable is the product; the orchestration is waste.** Ultimate
  steering is judged at the membrane where results meet the human: ranked,
  compressed, lead-first, calibrated, shaped to the next decision. Optimize the
  membrane and hide the machinery.

---

## Part III — The Session-Level Executive Loop (the conductor)

Above the task loop runs the **conductor**: a re-entrant control loop whose
controlled variable is not "is this task done" but "is my effort allocation and
my current frame still valid given everything that has streamed in." Re-entered on
exactly two events — **a returned subagent testimony** and **a new user message**
— and on each entry it *re-derives* the plan rather than resuming it.
Specified in full in the executive analysis; spec'd for `conductor.py` (above the
per-run `steering.py`). Per tick:

0. **HYDRATE** state from disk (ledger + last green commit), never from narrated
   memory. State that survives compaction is authoritative; context is a cache.
1. **CLASSIFY-THE-TURN** (the ignition gate). Conversational → answer solo, mint
   no run, log `suppressed:trivial`. Feasibility/build → emit a cheap **scout**
   whose result is a *hard precondition* for any expensive node. Rescope → fork
   the live frontier, don't replace it. **Spawn is a derived act, never a reflex.**
2. **RECONCILE-ON-EVENT** — diff new evidence against the premises of every open
   node; a result may DELETE a subtree, ADD an emergent leaf, RE-EDGE, or FORK.
   The plan is the loop's *state variable*, not its input.
3. **FOLD-CONSTRAINTS-FORWARD** — every runtime-learned fact (a concurrency cap, a
   thread-safety landmine, an upstream bug) becomes a durable constraint that
   mechanically re-routes all subsequent spawns. One fact, blast radius across
   prior decisions.
4. **SCHEDULE WITH LATENCY-HIDING** — partition pending work into result-dependent
   vs result-independent of every in-flight node; dispatch the independent
   partition into the shadow of the long pole. Idle wall-clock with a non-empty
   independent-ready set is an executive failure.
5. **GROUND-TRUTH ITS OWN INPUTS** — a contracts gate sits between "I have
   signatures" and "I write code": re-verify against real HEAD, not the diffs that
   motivated the build.
6. **CHECKPOINT THE SESSION** — each phase boundary is (tests-green AND
   committed); the unit of rollback is the increment, not the run.
7. **GOVERN AND RE-DECIDE** — run the governors; preempt/collapse/re-scope/abandon
   if any fires; then await the next event.

### Governors (each a control structure, not a sentence)
**Ignition** (convene/suppress) · **Frame-validity** (am I on the real ask) ·
**Evidence-vs-plan** (does this return invalidate the plan → rewrite topology) ·
**Contracts** (ground-truth my own foundations) · **Budget** (cumulative spend /
flat progress-derivative → collapse or preempt) · **Context-window** (offload
large outputs to disk, don't narrate) · **Disclosure** (auto-decide reversible,
batch the forking ones into one question) · **Durability** (no advance on
red/uncommitted; rollback-to-last-green on rescope).

> **The encoding principle:** every governor must be a *gate, a typed
> precondition, a scheduler tick, or a guard clause* — a place the harness can
> BLOCK or REDIRECT. Prose is advisory; the control loop is binding. This is
> where the conductor's judgment becomes non-bypassable — and the whole reason a
> weaker model can run ultracode and not be lazy: the structure won't let it.
