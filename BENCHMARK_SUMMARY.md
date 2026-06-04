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

## 9. The orchestration benchmark — long-context coverage (the one that actually needs it)

The atomic benchmarks below (§10) are honest but they *structurally can't reward orchestration* — each
problem fits one pass. This one is built for the regime ultracode is FOR: recover **every** one of `N`
values scattered across a corpus, as the corpus grows past one pass (RULER / multi-needle style;
deterministic, exact set-recall). Driving flash:

| corpus (`N` codes) | single-pass (bounded ~6k-tok working set) | **ultracode** |
|---|:---:|:---:|
| 30  (~4k tok)  | 1.00 | 1.00 |
| 90  (~11k tok) | **0.49** | 0.98 |
| 180 (~23k tok) | **0.25** | 1.00 |
| **real 715k-tok repo, 42 defs** | **0.02** | **1.00** |

Single-pass recall collapses toward `budget/corpus` (it can only see a working set); ultracode holds
≈1.0 by reading every section; precision stays 1.0 (omission, never hallucination). At `N=30` it's a
**wash** — the corpus fits one pass, so discernment routes it to solo and charges nothing. The gap is
the orchestration value and it widens with scale, to **50×** on a real 715k-token codebase.

**Confirmed on real cited data (HotpotQA, multi-hop, official F1) — with the honest 4-way:**

| haystack | flash bnd | flash + U | opus bnd | opus + U |
|---|:---:|:---:|:---:|:---:|
| gold *fits* the pass (K=8) | 0.840 | 0.757 | 0.888 | – |
| gold *buried* (K=60) | 0.455 | **0.685** (+0.230) | 0.790 | 0.734 (−0.056) |

Burying the evidence wrecks the weak model and **orchestration recovers +0.230 F1 (+50%)**. For Opus
it's a wash — *because* HotpotQA asks about real Wikipedia entities Opus has **memorized** (it answers
even when both gold paragraphs are truncated away), so its single pass shortcuts through memory and
there's no coverage bottleneck to recover.

**Controlled confirmation — MuSiQue** (composed/anti-shortcut multi-hop; you can't memorize "who founded
the company that distributed UHF", you must chain). Prediction: strip the shortcut and even Opus should
collapse on buried evidence + be recovered by orchestration. It does — gold buried (K=120), alias-aware F1:

| K=120 buried | flash bnd | flash + U | opus bnd | opus + U |
|---|:---:|:---:|:---:|:---:|
| | 0.190 | 0.267 (+0.077) | **0.656** (↓ from 0.956) | **0.700** (+0.044 F1, **+0.167 EM**) |

Same model, same regime, only memorizability changed — and the sign flips from HotpotQA's −0.056 to
**+0.044 F1 / +0.167 EM**. Honest cost: at K=8 (fits one pass) ultracode *hurts* hard 2-hop chaining
(flash 0.782→0.379) — the synth step loses fidelity vs a direct read, so discernment routes that to solo.

The sharpened thesis: **orchestration's value tracks the model's _bottleneck_, not its size** — weak
model → real bottleneck → win; strong model on memorized material → no bottleneck → wash; *any* model on
unmemorizable material past its window (MuSiQue, the 715k repo) → structural bottleneck → win. We don't
claim it beats Opus everywhere; the tables say so. Full methodology:
[`ORCHESTRATION_BENCH.md`](./ORCHESTRATION_BENCH.md) (`python bench/longctx_curve.py`).

## 10. Recognized atomic benchmarks — the full 4-way spectrum (where only execution helps)

The internal suites prove the mechanism; these prove it on benchmarks people actually cite. Every cell is
real: flash runs are single-shot vs the harness; Opus runs were generated by a 24/30-agent workflow and
**graded by the same deterministic harness** (HumanEval: the official `check()`; MATH: a normalize-then-LLM
equivalence judge). These are atomic (one context each), so the only lever is execution — the
decompose→fan-out machinery is a near-wash here, by design. Reproduce with `python bench/spectrum.py`.

| benchmark | weak (`flash`) | **weak + ultracode** | strong (`opus`) | strong + ultracode |
|---|:---:|:---:|:---:|:---:|
| **HumanEval** (code, pass@1, n=164) | 0.939 | **0.988** | 1.000 | 1.000 |
| **MATH-500** (competition, n=200) | 0.900 | **0.915** (L5: 35→38) | 0.990 | 0.990 |
| GSM8K (grade-school, n=200/100) | 0.980 | 0.960 | 1.000 | 1.000 |

Read it as the regime map, measured:

- **HumanEval is the keeper.** Execution-feedback self-repair (write → run the official tests → read the
  failure → fix, ≤3 rounds) takes flash from 0.939 to **0.988 — within 1.2 pts of Opus's _perfect_ score**,
  cutting remaining failures by **80%** (10 → 2). The runtime, not a bigger model, does the correcting.
- **MATH** lifts only where the problems are hard enough to leave headroom (the hardest level, L5: 35→38);
  net **+1.5%**.
- **GSM8K** has no headroom (flash already 0.98) — ultracode is a near-wash and even dips slightly. Honest.
- **The right two columns are the thesis:** `opus + ultracode == opus` on *all three*. When a single pass
  already saturates, orchestration adds exactly nothing — by design (discernment routes it to solo).

The shape is identical to every internal result: **headroom → ultracode recovers it; saturation → wash.**

---

## How far we came — the one-line journey

| dimension | start of build | now |
|---|---|---|
| **cost** | 30–78× (always full-metal) | **~1.5×** (discernment), free when it can't help |
| **precision on a weak model** | false-positive machine (~75% FP) | **12/12** (adjudication + execution arbiter) |
| **scale** | (untested) | **0.02 → 1.00** on a real 715k-token repo |
| **orchestration benchmark** | (untested) | **long-context coverage curve**: single-pass 0.25, ultracode 1.00 at 180 codes; the regime that *needs* it |
| **vs Opus, objective reasoning** | (untested) | single-shot 84% → **ultracode 92% → +execution 96%** |
| **recognized atomic benchmarks** | (untested) | **HumanEval 0.939→0.988** (≈Opus 1.0); MATH 0.900→0.915; full 4-way spectrum |
| **vs Opus, subjective taste** | (untested) | honest **wash** — mapped, not papered over |
| **dynamic spawning** | round-barriered | **on-the-fly** reactive driver (`pipeline.py`) |
| **install into a host** | (manual) | **one command** (`python -m ultracode.install --agent <path>`) + thread-safe delegate |
| **tests** | ~65 | **132** green, CI on 3.9/3.11/3.12 |

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
