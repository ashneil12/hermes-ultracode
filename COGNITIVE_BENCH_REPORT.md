# Cognitive head-to-head: Opus baseline vs DeepSeek+ultracode

**Question:** on genuinely reasoning-hard tasks (where a weak model's reasoning is the bottleneck),
how close does ultracode-on-DeepSeek-flash get to baseline Opus?

**Method.** 109 cognitively-hard tasks across 10 categories (deductive logic, quantitative, code-output
trace, subtle-bug-hunt, algorithm-reasoning, causal/counterfactual, proof-flaw-detection, constraint-
planning, lateral-insight, multi-hop inference), each generated and **independently verified** (every
answer re-derived from scratch, code executed) so the ground truth is objective. Three solvers, scored
the same way: **Opus** (me, solving directly = the baseline), **DeepSeek-flash single-shot**, and
**DeepSeek-flash + ultracode** (the harness: decompose → fan out → verify → synthesize).

**Scoring.** Crisp-answer tasks (numbers, names, outputs) are keyword-scored against ground truth.
Paragraph-answer tasks (find-the-bug, find-the-flawed-step, derive-the-complexity) and any crisp task a
solver got marked wrong are re-scored by an **LLM judge** against ground truth, anonymized and judged on
substance — because keyword matching systematically **under**-counts correct-but-terse answers (ultracode's
synthesis says "B", the signature wanted "B is the Spy"). Keyword-*true* matches are trusted (specific
signatures don't false-positive).

## Result

| solver | score | ratio vs Opus |
|---|---|---|
| **Opus baseline (me)** | **109 / 109 = 1.000** | — |
| DeepSeek-flash single-shot | 92 / 109 = 0.844 | **84.4 %** |
| **DeepSeek-flash + ultracode** | **100 / 109 = 0.917** | **91.7 %** |

**ultracode-flash reaches 91.7 % of baseline Opus, +7.3 points over single-shot flash** — above the
70–80 % target. (Naive keyword-only scoring read 0.79; it was an artifact of penalizing ultracode's terse
synthesized answers, which the judge corrected.)

### Per category (correct / n)

| category | Opus | flash single-shot | flash + ultracode |
|---|---|---|---|
| deductive_logic | 12/12 | 10/12 | 11/12 |
| quantitative_reasoning | 12/12 | 12/12 | 12/12 |
| code_output_trace | 12/12 | 11/12 | 11/12 |
| subtle_bug_hunt | 10/10 | 9/10 | 10/10 |
| algorithm_reasoning | 10/10 | 7/10 | 8/10 |
| causal_counterfactual | 12/12 | 8/12 | **12/12** |
| proof_flaw_detection | 10/10 | 10/10 | 9/10 |
| constraint_planning | 12/12 | 11/12 | 11/12 |
| lateral_insight | 12/12 | 8/12 | **10/12** |
| multi_hop_inference | 7/7 | 6/7 | 6/7 |

### What ultracode did and didn't fix
- **Biggest lifts where the harness helped:** causal_counterfactual (8→12) and lateral_insight (8→10) —
  multi-step simulation/induction tasks (pirate game, cyclic XOR at step 100, water-jug min-pours) where
  the decompose-and-verify discipline kept flash from a one-pass slip. It also **filled in empty answers**
  the single-shot left blank on hard paragraph tasks.
- **The 9 remaining ultracode failures cluster on SEARCH / COMPUTE tasks:** `binary-digit-multiple` (BFS
  over remainders), `two-jug-six-liters` (BFS over states), `hazmat-knapsack` (constrained knapsack),
  `factorial-trailing-zeros` (solve z(n)≥100). These need systematic enumeration a language model can't do
  reliably in-head — but flash can *write correct code for them*. The harness has `run_python` but only
  uses it for the finding-arbiter, not as a reasoning aid. **Wiring execution into solving is the next
  lever** (see the gap-closing work).

**Honest caveat:** reasoning quality is genetics; the harness narrows the gap (structure, verification,
not-leaving-blanks), it doesn't replace model intelligence. 91.7 % is the ceiling of what *this* harness
extracts from flash on these tasks today.

## Execution as a reasoning aid — a wash (an honest negative result)

The 9 remaining failures clustered on search/compute. An isolated test confirmed the lever works:
letting flash WRITE+RUN a program solved **9/10** of those (it wrote a BFS and found the 12-digit binary
multiple of 2026, computed the constrained knapsack = 90, the min jug-pours = 10). So I wired `compute.py`
into the harness (`execution_assist`): the agent writes+runs code for computable tasks, declines for the rest.

**But on the full bank it was a WASH: 0.908, actually −1 vs the 0.917 non-exec.** It *won* the pure-compute
tasks (knapsack solved, deductive enumeration 11→12) but *lost* an equal amount where the agent **misapplied**
compute — it computed a value for a find-the-**bug** task ("[[2,4]]" instead of naming the defect), and printed
only **one part** of multi-part questions (the XOR config without the count; one knight's type out of three).

**The lesson (the real finding):** naive *short-circuit-to-compute* is wrong — execution should **augment**
reasoning, not **replace** it, and must decline explain/identify tasks and emit *complete* multi-part output.
A **v2** prompt (decline EXPLAIN/IDENTIFY/JUSTIFY; print every part) **fixed both failure modes** — verified:
the XOR task now prints config *and* count; the 3-type knights puzzle now correctly *declines* compute and
reasons all three types; the find-the-bug task declines compute. Compute-mode use dropped 58→38 (the agent
now picks it more appropriately). But v1/v2 still *short-circuited* to the program's output, capping
the gain. **v3 — compute-as-EVIDENCE — is the design that wins.**

### v3: execution as evidence, not replacement (the win)
Instead of returning the program's output as the answer, v3 **folds the computed value into the material as
authoritative evidence** and lets the normal reasoning flow produce the COMPLETE answer + explanation (and
override an obviously-wrong computation). This captures the compute wins with **no** downside:

| config | fair score | vs Opus |
|---|---|---|
| non-exec ultracode (conservative shipping default) | 100/109 = 0.917 | 91.7 % |
| exec v1 (short-circuit-to-compute) | 0.908 | wash |
| **exec v3 (compute-as-evidence)** | **105/109 = 0.963** | **96.3 %** |

v3 lifts `lateral_insight` 10→**12/12** (the binary-multiple and jug-search tasks flash can't reason are now
solved by the folded-in computed value), `constraint_planning` to **12/12** (the constrained knapsack), and
`causal_counterfactual` to **12/12** — while losing nothing, because compute only ever *augments*. The 4
remaining misses are genuinely-hard non-compute reasoning. **`execution_assist` stays off by default** (it
runs model-generated code — same safety posture as `execution_verify`), but **with it on, ultracode-flash
reaches 96.3 % of Opus** — it's the recommended config wherever code execution is safe (sandbox/trusted).

## On grading the reasoning *process*, not just the answer

The LLM judge scores **substance**, not keyword overlap — for find-the-bug / which-step-is-wrong it required
naming the same essential defect/step, and for multi-part it required completeness (catching the compute-mode
partial answers above). For compute-mode answers the "reasoning" *is* the program — verifiable by construction.
For the subjective benchmark (next), where there's no single answer, the **process** is graded directly: the
judge-panel trace (the N candidate angles → critique → graft) is what's evaluated, not just the final text.
