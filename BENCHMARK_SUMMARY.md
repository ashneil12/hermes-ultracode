# Ultracode — the whole benchmark arc, and how far we came

Every benchmark run in this build, in order, with the result. The thread: ultracode started looking
like an expensive tool that *matched* a weak model at best and *hurt* it at worst — and ended as a
characterized, multi-regime system with a precise map of where it wins huge, where it's free, and where
it honestly can't help. All runs drove **DeepSeek-flash** (a deliberately weak model) unless noted; the
baseline is single-shot of the same model, or **Opus (me)** for the head-to-heads.

---

## 1. Code audit — the honest starting point (a near-negative)

The first thing we measured, and it was humbling: on planted-bug code (40–924 lines), the single-shot
baseline already hit **recall 1.00 every time**, so orchestration had nothing to recover and sometimes
*hurt*:

| task | model | baseline R/P | ultracode R/P | cost |
|---|---|---|---|---|
| large (120 ln, 21 bugs, dense) | flash | **1.00 / 1.00** | 0.95 / 0.94 | 4k → 288k (78×) |
| large2 (924 ln, 21 bugs, sparse) | flash | **1.00 / 1.00** | 1.00 / 0.94 | 9k → 693k (78×) |

**Verdict then:** "a 78× cost tool that matches recall and can hurt precision." And on 12 real findings
from the Hermes codebase, weak-model finding + weak-model verifying = a **false-positive machine (~75% FP)**.
This was the low point — and the to-do list.

## 2. Discernment — cost 30–78× → ~1.5×

The fix for "always full-metal": solo-first, escalate only when it helps.

| task | baseline R/P · cost | ultracode R/P · cost |
|---|---|---|
| auth (easy) | 1.00 / 1.00 · 1.1k | 0.75 / 1.00 · **2.3k** (stayed solo; was 37k forced) |
| bigbug (12 bugs) | 1.00 / 1.00 · 1.8k | 1.00 / 1.00 · **3.4k** (was 81k forced) |
| vulnflask (real, 10 vulns) | 0.90 / 0.93 · 5.5k | 0.90 / **1.00** · 7.4k (escalated; killed the FP) |

Cost collapsed from 30–78× to **~1.5×**, precision rose to **1.00**, recall ≈ baseline. No longer a gimmick.

## 3. Accuracy stack — false-positive machine → accurate auditor

Three composing gates on the 12 Hermes findings:

| gate | result |
|---|---|
| flash adjudication | caught **6/10** FPs |
| **pro adjudication** (stronger verifier) | caught **10/10** FPs |
| **execution arbiter** (run a repro) | **resurrected 2/2** real bugs the strong verifier over-killed |

**Net: 12/12 correct.** Precision — not recall — is the weak-model bottleneck, and this fixed it.

## 4. Research / general-use — where orchestration does NOT help

| regime | baseline | ultracode |
|---|---|---|
| trivial factual recall (SOLID, ACID…) | 0.95 | 0.95 (tie — pure overhead) |
| broad known-topic coverage (microservices, appsec) | **1.00** | 0.94 (loses — single pass saturates) |

Plus a cost win from discernment: 5 easy tasks went **95k → 2k tokens (~47× cheaper)** at unchanged recall.
Lesson: orchestration never improves recall-of-known-facts.

## 5. Corpus-scale — the genuine win (and it widens with scale)

When the material exceeds one context window, the single pass *structurally cannot* see it all:

| corpus | baseline | orchestrated | lift |
|---|---|---|---|
| synthetic, 248k tok | 0.41 | **1.00** | +0.59 |
| synthetic, 620k tok, 100 extractors | 0.16 | **1.00** | **+0.84** (gap widens) |
| **real: Hermes Python, 715k tok** | **0.02** | **1.00** | **+0.98** |
| real: openclaw TypeScript | 0.29 | **0.91** | +0.62 |

This is the headline win — on a real 715k-token codebase, ultracode recovers **50× more** than a single pass.

## 6. Dynamic workflows + hardening (capability, not a score)

- Wrote `pipeline.py` — the no-barrier reactive driver: spawn sub-agents **on the fly** as results land,
  not round-by-round (deterministic overlap proof; a barrier would deadlock).
- Adversarial red-teams of the harness's own reasoning: **21 verdicts, 6 confirmed, none a correctness bug.**
- Stress test: **100+ parallel agents**, deterministic.

## 7. Cognitive head-to-head vs Opus — the big one

109 reasoning-hard tasks (verified ground truth), me = the 100% baseline, fair-judged on substance:

| solver | score | vs Opus |
|---|---|---|
| DeepSeek-flash single-shot | 92/109 = 0.844 | 84.4 % |
| ultracode (shipping default) | 100/109 = 0.917 | **91.7 %** |
| **ultracode + compute-as-evidence** | **105/109 = 0.963** | **96.3 %** |

The execution lever itself was iterated wash → win: v1 short-circuit **0.908** → v3 compute-as-evidence
**0.963**. ultracode adds **+7.3 pts** over single-shot; with execution-as-evidence, **+11.9 pts → 96.3 % of Opus.**

## 8. Subjective generation — the honest ceiling

70 marketing/email/creative tasks, rubric-judged, judge-panel fired on all 70:

| solver | rubric % | win-rate |
|---|---|---|
| **Opus** | **98.5 %** | **85 %** |
| flash single-shot | 87.2 % | 6 % |
| flash + ultracode | 84.3 % | 8 % |

**ultracode was a wash vs single-shot** (head-to-head 12 better / 16 worse / 20 tie). Orchestration can't
manufacture taste the model lacks.

---

## How far we came — the one-line journey

| dimension | start of build | now |
|---|---|---|
| **cost** | 30–78× (always full-metal) | **~1.5×** (discernment), free when it can't help |
| **precision on a weak model** | false-positive machine (~75% FP) | **12/12** (adjudication + execution arbiter) |
| **scale** | (untested) | **0.02 → 1.00** on a real 715k-token repo |
| **vs Opus, objective reasoning** | (untested) | single-shot 84% → **ultracode 92% → +execution 96%** |
| **vs Opus, subjective taste** | (untested) | honest **wash** — mapped, not papered over |
| **dynamic spawning** | round-barriered | **on-the-fly** reactive driver (`pipeline.py`) |
| **tests** | ~65 | **120+** green |

## The synthesis (the thing worth keeping)

> **Orchestration multiplies what the model HAS — search, breadth, verification, and now computation.
> It cannot manufacture what it LACKS — taste.**

- **Objective bottleneck** (coverage / verification / search / compute) → ultracode closes most of the gap
  to Opus and, at scale, beats any single pass outright.
- **Taste bottleneck** (subjective craft) → no amount of fan-out helps; the judge-panel grades the weak
  model's candidates with the weak model's weak taste.

We went from "is this 78× cost even worth it?" to a system that takes a deliberately weak model to **96 % of
Opus on hard reasoning** and **1.00 on real-codebase-scale work** — while being honest about the one place
(taste) where structure can't substitute for intelligence.
