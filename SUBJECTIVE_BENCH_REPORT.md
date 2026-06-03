# Subjective generation: Opus vs DeepSeek+ultracode (judge-panel)

**Question:** on subjective writing — marketing copy, emails, creative writing, rhetoric, naming,
UX microcopy — where quality is craft and taste, does ultracode's judge-panel (generate N candidates
from different angles → score → synthesize-the-winner-grafting-runners-up) lift a weak model toward
Opus? This is the blog's "exploration and taste" regime, the one most expected to *need* orchestration.

**Method.** 70 verified subjective tasks across 6 categories, each with a 4-6 item **quality rubric**
and objective **hard constraints** (word/line limits, must-include, banned words, format). Three
solvers: **Opus** (single best pass = baseline), **DeepSeek-flash single-shot**, **DeepSeek-flash +
ultracode** (judge-panel — fired on **all 70** tasks). A blind judge scored each anonymized output:
rubric criteria met, constraint compliance (counts/bans actually checked), and the single best on craft.
(48 of 67 tasks returned complete judge verdicts.)

## Result

| solver | rubric % | constraint % | win-rate |
|---|---|---|---|
| **Opus baseline** | **98.5 %** | 91.7 % | **85.4 %** (41/48) |
| DeepSeek-flash single-shot | 87.2 % | 81.2 % | 6.2 % |
| DeepSeek-flash + ultracode | 84.3 % | 83.3 % | 8.3 % |

Two findings, and the second is the interesting one:

1. **Opus dominates subjective writing.** 85 % head-to-head win-rate, near-perfect rubric. Craft and
   taste are genetics; the gap to flash is large and real (the rubric criteria are concrete — distinct
   angles, no clichés, constraint compliance — not just judge vibe).

2. **ultracode did NOT beat single-shot flash on subjective quality.** Head-to-head on rubric coverage:
   ultracode better on **12** tasks, single-shot better on **16**, tied on **20** — a wash, if anything a
   slight regression. The only category where the judge-panel showed life was **naming_branding** (3 wins
   vs Opus's 6) — the most *tournament-shaped* task, where "generate many → select" applies most directly.

## The insight — orchestration helps objective bottlenecks, not taste

Put beside the cognitive benchmark, the two results are a clean complement:

| regime | bottleneck | ultracode vs single-shot flash |
|---|---|---|
| **cognitive** (objective answers) | coverage / verification / search | **+7.3 pts** (helps — 91.7 % of Opus) |
| **subjective** (craft) | **taste** (recognizing the good one) | **~0** (wash) |

The judge-panel generates more candidates, then **uses flash's own taste to score and graft them** — and
flash's taste is exactly the weak link. Generating five candidates doesn't help if the selector can't tell
which is best, and the synthesis step can even dilute a clean winner. **You can't orchestrate your way to
taste you don't have.** Orchestration multiplies a capability the model already has (search, verification,
breadth); it can't manufacture one it lacks (judgment of quality).

This is *why* the cognitive benchmark worked and this one didn't: there, the harness added **structure and
verification** to objective reasoning; here, the missing ingredient is **taste**, which no amount of
fan-out supplies when the judge is the same weak model.

## The lever that would actually help (documented, untested here)

"Discover cheap, **judge strong**" — applied to taste. Let flash generate the N candidates (cheap, broad),
but have a **stronger model do the scoring/selection/refinement** in the judge-panel. That puts taste where
the bottleneck is, the same way pro-adjudication fixed the false-positive problem in the code audit. We
benchmarked flash-only (the judge-panel's scorer was flash), so this is the next experiment, not a result.

## Caveat
The judge is an Opus agent; it could mildly prefer Opus-style prose, inflating the 85 % win-rate. But the
**load-bearing finding — ultracode ≈ single-shot on subjective — is immune to that**, since both are flash
outputs (the judge has no model-style reason to favor one flash piece over another). And the rubric gap is
on objective criteria, not vibe.
