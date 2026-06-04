# Benchmarks that actually require orchestration

> **The point.** GSM8K / HumanEval / MATH are *atomic* — each problem fits in one context window, so a
> single focused pass can solve them and orchestration has nothing to recover. (On those, ultracode's
> only lever is *execution* — running code — which is why HumanEval lifts but the decompose→fan-out→
> verify machinery is a near-wash. See [`BENCHMARK_SUMMARY.md`](./BENCHMARK_SUMMARY.md) §9.) Those
> benchmarks **cannot** reward orchestration; they were never going to.
>
> Orchestration earns its cost in exactly one regime: **when the work exceeds what one focused pass can
> hold.** This document is a benchmark built to live in that regime, with the methodology written out so
> it's reproducible and honest about where the win is — and isn't.

## The benchmark: long-context multi-value retrieval (RULER / multi-needle style)

A synthetic, fully-controllable, exactly-scored coverage task (the construction RULER and the
needle-in-a-haystack suites use, so there's no dataset to trust and the scaling axis is a dial):

- **Corpus.** `N` short "memo" documents of innocuous prose. Every document carries exactly one
  *clearance code* of the form `The clearance code for Project <Name> is CLR-XXXXXX.` (a `CLR-` prefix +
  6 chars). So there are `N` codes to recover, scattered across the corpus. Deterministic by seed; zero
  external data.
- **Task.** *"Find EVERY clearance code anywhere in the corpus and list them all."* Pure coverage.
- **Scoring.** Exact set recall = `|found ∩ planted| / |planted|`, and precision = `|found ∩ planted| /
  |found|`. Codes are regex-extractable and unique, so scoring is deterministic — no judge, no model in
  the grader.

`N` (documents = codes) is the **context-pressure axis**. As `N` grows, the corpus grows past what one
pass can hold, and the task is the same: recover *all of it*.

### Three conditions

| condition | what it is |
|---|---|
| **single — native** | the whole corpus in one prompt, the model's raw long-context window, asked to list everything |
| **single — bounded** | one pass under a *declared working-set budget* `B ≈ 6k tokens` (24k chars) — the realistic agent-turn regime, where you don't (and often can't) dump the whole corpus into one call. Corpus beyond `B` is unseen. |
| **ultracode** | chunk the corpus into sections (≤ 8 memos each), **fan out one extractor per section** (each lists only its section's codes — a trivially complete sub-task), then reconcile the union |

The **bounded** baseline is the honest center of gravity: it's not a handicap, it's the *premise of the
whole field*. Retrieval, RAG, and agent loops all exist because you operate on a bounded working set per
step. The benchmark asks: under that bound, can you still recover everything? A single pass can't —
it sees `min(L, B)`. ultracode can — it reads every section.

## Results (driving DeepSeek-flash; recall = codes recovered / planted)

| corpus (`N` codes) | total size | single — native | single — bounded (`B`≈6k tok) | **ultracode** |
|---|---|:---:|:---:|:---:|
| 30 | ~16k chars (~4k tok) | 1.00 | **1.00** | 1.00 |
| 90 | ~46k chars (~11k tok) | 1.00 | **0.49** | 0.98 |
| 180 | ~94k chars (~23k tok) | 1.00 \* | **0.25** | 1.00 |
| **real 715k-token repo, 42 defs** | 715k tok | **0.02** | — | **1.00** |

\* native is competent *within* the window but hits a **stochastic cliff** — a rerun at 180 codes
dropped to **0.32** recall. The bounded baseline's collapse is deterministic; native's is a coin-flip
you can't schedule around. The last row is the real-codebase extreme (`bench/corpus_*.py`): at 715k
tokens, one pass sees 1 of 42 scattered definitions — orchestration is the only thing that recovers
the rest.

Precision stays **1.00** for the single-pass conditions throughout — the failure is pure *omission*
(coverage lost to truncation / the long-list dilution effect), never hallucination. ultracode's
precision is ~1.0 (occasional single extraction-noise code, reconciled away).

### How to read it (the honest regime map, measured)

- **Where the corpus fits one pass** (small `N`): a **wash** — single-pass and ultracode both ≈ 1.0.
  This is the discernment story: *route to solo, don't pay for orchestration you don't need.* ultracode's
  triage does exactly this.
- **Where the corpus exceeds the pass** (growing `N`): bounded single-pass recall **collapses toward
  `B / L`** (it can only see a budget's worth), while ultracode **holds ≈ 1.0** by reading every section.
  The gap is the orchestration value, and it **widens monotonically with corpus size**.
- The model's **native** window is genuinely competent for a while (flash holds to ~94k tokens), then
  hits a stochastic cliff (a single run dropped to 0.32 recall at 180 codes). Orchestration converts that
  stochastic, scale-dependent failure into a deterministic ~1.0.

This is the same shape as the harness's real-world result: on a **715k-token production codebase**, a
single pass recovers **1 of 42** scattered class definitions (0.02); 286 chunk-extractors recover **all
42** (1.00). (`bench/corpus_*.py`, `ultracode/corpus.py`.) The synthetic curve is the controlled
explanation of that real win.

## The same regime on real, cited data: HotpotQA multi-hop

To show this isn't a synthetic artifact, we run the identical bounded-pass setup on **HotpotQA**
(a recognized multi-hop QA benchmark — answers require chaining facts across 2 gold Wikipedia
paragraphs). The standard distractor setting gives 10 paragraphs, which fits one pass; we reproduce the
*fullwiki* reality by burying the 2 gold paragraphs among `K` distractors drawn from a shared pool, then
score the **official HotpotQA answer F1 / EM** (SQuAD normalization). `n=20` questions, driving flash:

| haystack | size | single — bounded (`B`≈6k tok) | **ultracode** | Δ F1 |
|---|---|:---:|:---:|:---:|
| `K=8` distractors (gold fits the pass) | ~5k chars | F1 **0.840** / EM 0.650 | F1 0.757 / EM 0.600 | **−0.083** |
| `K=60` distractors (gold buried at ~27k chars) | ~35k chars | F1 **0.455** / EM 0.350 | F1 **0.685** / EM 0.500 | **+0.230** |

This is the regime map as a **crossover**, on real data. At `K=8` the evidence fits one pass, so
ultracode's extract→reconcile→synthesize pipeline is *slightly worse* than a direct read (−0.083 F1) —
the wash-when-it-fits case discernment routes to solo, so in practice you never pay it. At `K=60` the
gold paragraph sits *past* the working set; the bounded pass can't reach it and F1 nearly halves
(0.840 → 0.455), while ultracode reads every section and recovers it — **+0.230 F1 (+50% relative),
+0.150 EM**. Orchestration flips from liability to asset exactly at the point the work exceeds one
pass. Same shape as the synthetic curve, on questions people actually cite. Reproduce:
`python bench/data/fetch_hotpot.py && python bench/multihop_bench.py ultracode deepseek-v4-flash`.

### The full spectrum — and the honest reason a frontier model is different

Running the same setup on **Opus** (`n=12`, base = one bounded pass, ultra = Opus readers fanned out
over the sections + a synthesizer) gives the 4-way picture (answer F1):

| haystack | flash — bounded | flash + ultra | opus — bounded | opus + ultra |
|---|:---:|:---:|:---:|:---:|
| `K=8` (gold fits the pass) | 0.840 | 0.757 | 0.888 | — |
| `K=60` (gold buried) | **0.455** | **0.685** (+0.230) | **0.790** | 0.734 (−0.056) |

Read this carefully — it's the most honest thing in this repo. For **flash**, burying the evidence is
devastating (0.840 → 0.455) and orchestration recovers it. For **Opus**, burying the evidence barely
dents it (0.888 → 0.790) and orchestration is a **wash** (−0.056 F1, identical 0.583 EM). Why the
difference? **Parametric knowledge.** HotpotQA asks about *real* Wikipedia entities, and we verified
that on questions where *both* gold paragraphs fall outside the budget, Opus still answers correctly
(it knows from training that *Animorphs* is the first-person YA series, that Derrickson and Wood are
both American). So for a strong model HotpotQA's "bounded pass" isn't evidence-bound at all — the
single pass shortcuts through memory, there is no coverage bottleneck, and orchestration has nothing to
recover. This is a known limitation of HotpotQA with capable models, and it's exactly why the
**synthetic** benchmark (unmemorizable random codes) and the **715k-token repo** (unmemorizable
specifics at a scale past any window) are the clean tests: there the collapse is *structural*, for any
model, and orchestration is the only recovery.

**The sharpened thesis: orchestration's value tracks the model's _bottleneck_, not its size.** A weak
model has a real coverage bottleneck early → big win. A strong model on material it has memorized has no
bottleneck → wash (route to solo). *Any* model on unmemorizable material exceeding its window has a
structural bottleneck → win. We don't claim "orchestration beats Opus everywhere" — it doesn't, and the
table says so. We claim it recovers coverage wherever a single pass genuinely can't.

### MuSiQue — the controlled confirmation (remove the shortcut, the frontier model needs it too)

That thesis makes a falsifiable prediction: *if* the HotpotQA wash for Opus is really a memorization
shortcut, then on a benchmark Opus **can't** memorize, burying the evidence should hurt even Opus, and
orchestration should recover it. **MuSiQue** is exactly that benchmark — its questions are *composed*
("the spouse of the Green performer", "who founded the company that distributed UHF") so you must chain
the evidence; there's no single fact to recall. Same setup, gold buried among `K=120` distractors,
alias-aware F1 (Opus `n=12`, flash `n=20`):

| haystack | flash — bounded | flash + ultra | opus — bounded | opus + ultra |
|---|:---:|:---:|:---:|:---:|
| `K=8` (gold fits the pass) | 0.782 | 0.379 | 0.956 | — |
| `K=120` (gold buried) | **0.190** | 0.267 (+0.077) | **0.656** | **0.700** (+0.044 F1, **+0.167 EM**) |

The prediction holds. Strip the shortcut and **Opus's bounded pass collapses too** (0.956 → 0.656,
versus shrugging off HotpotQA at 0.790), and orchestration **recovers** it (+0.044 F1, +0.167 EM) —
the opposite sign from HotpotQA's −0.056. Same model, same regime; the only thing that changed is
whether the answer was memorizable. That is the bottleneck thesis, controlled.

And the honest cost, in plain sight: at `K=8`, where everything fits one pass, ultracode *hurts*
(flash 0.782 → 0.379). Composed 2-hop chaining is exactly where the extract→reconcile→synthesize
pipeline loses fidelity versus a direct read — the synthesizer must re-chain fragmented per-section
facts. So the K=120 wins are real but *bounded by the synthesis step*: orchestration wins because the
single pass collapses **below** that ceiling, not because the pipeline is lossless. Discernment routes
the fits-one-pass case to solo precisely to avoid paying this. We report it because it's true.

## Pure coverage on real data: NER and symbol enumeration (no reasoning confound)

The multi-hop benchmarks above mix *reasoning* (chaining) into the task, which muddies the orchestration
signal (and lets a strong model shortcut via memory). The cleanest test of the coverage regime strips
reasoning out entirely: **enumerate every X across a corpus**, where recognizing a single X is trivial and
the whole difficulty is *missing none*. Two such tasks, both real, both exactly scored, driving flash:

**Named-entity coverage (CoNLL-2003, recognized NER benchmark).** List every PERSON/ORG/LOCATION across a
growing corpus; gold from the dataset labels; metric = entity-set recall.

| corpus | gold entities | single-pass (bounded ~6k tok) | **ultracode** (enumerate → union) |
|---|:---:|:---:|:---:|
| 100 sentences (~4k tok) | 125 | 0.92 | 0.92 — wash (fits) |
| 400 sentences (~11k tok) | 487 | 0.83 | 0.94 |
| 1000 sentences (~23k tok) | 970 | **0.40** | **0.91** |
| 2000 sentences (~45k tok) | 1619 | **0.23** | **0.87** |

**Symbol coverage (real codebase, AST-exact gold).** "List every function and class defined in this repo"
— the literal agent task (*audit this module*, *find all callers*). Corpus = the 27-file, 223k-char
`ultracode/` package; gold = every `def`/`class` from the AST.

| corpus | gold symbols | single-pass (sees 24k/223k = 11%) | **ultracode** (one reader per file) |
|---|:---:|:---:|:---:|
| 223k-char real package | 196 | **0.07** (14/196) | **0.96** (189/196) |

Same shape as everything else, now with **zero reasoning confound and exact ground truth**: a wash where
the corpus fits one pass, a widening collapse-vs-hold where it doesn't, out to **13.5×** on the real
codebase. Precision is clean — the non-gold emissions are real qualified names (`TaskGraph.add`), not
hallucinations; orchestration recovers coverage without spraying. (Single-shot points are high-variance;
`bench/ner_coverage_bench.py … <runs>` averages for a stable headline.)

### These benchmarks rebuilt the harness, not just scored it

Running them surfaced real harness bugs that are now fixed (the benchmark as *instrument*, not just
scoreboard) — the symbol task went from a capped 0.47 to 0.96 as each was fixed:

- **Adaptive worker budget + empty-retry.** A reasoning-model sub-agent can spend its whole token budget
  *thinking* and return empty (`finish_reason=length`), silently dropping its chunk from the union.
  `delegate_fanout` gained `retry_empty` (re-dispatch only the holes), `aux_call` escalates its budget on
  an empty return, and the host bridge escalates the per-worker budget — so a starved worker can't quietly
  cap recall.
- **`enumerate_corpus`** — a first-class map-reduce-**union** primitive for total-coverage asks, which the
  salience-capped findings path of `research_corpus` structurally under-recovered.
- **Fits-one-pass guard** — chunk→fan-out fragments evidence that must be chained, so both corpus
  primitives now do one combined read when the corpus fits (no lossy fan-out without a coverage benefit).
- **Robust list parsing** — workers emit messy output; the union now splits inline comma/semicolon lists
  (which were collapsing to one item and cratering recall) and drops preamble/headers/label-prefixes
  (which were leaking in as fake items).

## Why this is the benchmark that matters for "should I install this?"

An agent's hard problems are rarely one tidy prompt — they're *audit this 50-file module*, *find every
caller of this pattern across the repo*, *synthesize an answer from a dozen documents*. Every one of
those is a coverage-over-a-corpus task, and every one degrades in a single pass the way these benchmarks
degrade. ultracode is the harness that turns "saw a fraction" into "read all of it," **deterministically**
— and the symbol-coverage row (0.07 → 0.96 on a real codebase) is that exact task, measured.

## Reproduce

```bash
# the scaling sweep (reads its key from $DEEPSEEK_API_KEY or ~/.ultracode-bench/deepseek.env)
python bench/longctx_bench.py single        deepseek-v4-flash   # native long-context
python bench/longctx_bench.py single_budget deepseek-v4-flash   # bounded working set (the regime)
python bench/longctx_bench.py ultracode     deepseek-v4-flash   # chunk -> fan-out -> reconcile
python bench/longctx_curve.py deepseek-v4-flash                 # the combined curve

# pure-coverage on real data (exact gold, no reasoning confound)
python bench/data/fetch_conll.py                                 # fetch CoNLL-2003 NER (CC BY-SA)
python bench/ner_coverage_bench.py single_budget deepseek-v4-flash 3   # 3-run average
python bench/ner_coverage_bench.py ultracode      deepseek-v4-flash 3
python bench/ner_curve.py deepseek-v4-flash
python bench/symbol_coverage_bench.py ultracode deepseek-v4-flash      # "find every symbol" on a real repo

# the real-corpus analog (point it at any large checkout)
python bench/corpus_real.py /path/to/a/large/repo
```

Everything is deterministic by seed; the corpus generator (`bench/longctx_bench.py:make_corpus`) plants
`N` unique codes across `N` memos and the grader is exact set arithmetic. The NER/symbol graders score
against dataset labels / the AST — no model in the loop.
