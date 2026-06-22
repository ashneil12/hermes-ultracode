# hermes-ultracode

[![ci](https://github.com/ashneil12/hermes-ultracode/actions/workflows/ci.yml/badge.svg)](https://github.com/ashneil12/hermes-ultracode/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![deps](https://img.shields.io/badge/third--party%20deps-0-success)
![tests](https://img.shields.io/badge/tests-132%20passing-success)
![license](https://img.shields.io/badge/license-see%20LICENSE-lightgrey)

A deterministic **orchestration harness** that makes a weak model punch above its weight on hard
tasks — by wrapping it in *decompose → fan-out → adversarially verify → synthesize*, and by
**reasoning out its own method** rather than following a hardcoded recipe.

Ported from the "ultracode" mode of Claude Code into a self-contained, runtime-agnostic Python
package. It drives any backend you give it (a frontier model, a local model, or a cheap/weak one)
through two injected callables — **no third-party dependencies, only the standard library.**

## Install as a Hermes skill (one command)

This repo is also a **drop-in skill for any Hermes agent** — it ships the doctrine, the
auto-firing skill, AND the engine, fully self-contained. Point an agent at it and run:

```bash
git clone https://github.com/ashneil12/hermes-ultracode.git \
  && cd hermes-ultracode && ./install.sh
```

Or tell your Hermes agent: **"clone https://github.com/ashneil12/hermes-ultracode and run install.sh"**.

That installs the skill + engine into `~/.hermes/skills/` (user-data, so it **survives upstream
desktop-app updates**). The skill then auto-fires on substantive tasks (audits, find-all sweeps,
design decisions, high-stakes work) — you don't invoke it; it engages when the work warrants it.
Trigger words `ultracode` / `ultrathink` / `go all in` force maximum rigor explicitly. The
deterministic gate and `enumerate_corpus` work with zero extra setup. See `skill/SKILL.md`.

## The headline — a benchmark that actually requires orchestration

Atomic benchmarks (GSM8K/HumanEval/MATH) *can't* reward orchestration: each problem fits in one
context window, so a single pass already solves it. Orchestration earns its cost in one regime —
**coverage when the work exceeds what one focused pass can hold.** So here is a benchmark built to
live there: recover *every* one of `N` values scattered across a corpus, as the corpus grows
(RULER / multi-needle style; deterministic, exactly scored). Driving DeepSeek-flash, **recall**:

| corpus (`N` codes) | single-pass (bounded ~6k-tok working set) | **ultracode** (chunk → fan-out → reconcile) |
|---|:---:|:---:|
| 30  (~4k tok)  | 1.00 | 1.00 |
| 90  (~11k tok) | **0.49** | 0.98 |
| 180 (~23k tok) | **0.25** | 1.00 |
| **real 715k-tok repo, 42 defs** | **0.02** | **1.00** |

> As the corpus exceeds one pass, single-pass recall **collapses toward `budget / corpus`** — it can
> only see a working set's worth — while ultracode **holds ≈ 1.0** by reading every section. The gap
> *is* the orchestration value, and it **widens with scale**, to 50× on a real 715k-token codebase.
> Precision stays 1.0 throughout: the single-pass failure is pure *omission*, never hallucination.

And the honesty that makes it trustworthy: at `N=30`, where the corpus fits one pass, it's a **wash**
(1.00 vs 1.00) — ultracode's discernment *routes that to solo and charges you nothing*. Full
methodology + reproduction in [`ORCHESTRATION_BENCH.md`](./ORCHESTRATION_BENCH.md)
(`python bench/longctx_curve.py`).

**Confirmed on real, cited data — HotpotQA** (multi-hop QA, official F1, gold paragraphs buried in a
distractor haystack). Full 4-way spectrum, and the honest reason a frontier model differs:

| haystack | flash bnd | **flash + U** | opus bnd | opus + U |
|---|:---:|:---:|:---:|:---:|
| gold *fits* the pass (K=8) | 0.840 | 0.757 | 0.888 | – |
| gold *buried* past it (K=60) | 0.455 | **0.685** (+0.230) | 0.790 | 0.734 (−0.056) |

For the weak model, burying the evidence is devastating and **orchestration recovers +0.230 F1
(+50%)**. For Opus it's a *wash* — but only because HotpotQA asks about *real* Wikipedia entities Opus
has **memorized**, so its single pass shortcuts through training (verified: it answers correctly even
when both gold paragraphs are truncated away). HotpotQA can't test the coverage regime for a strong
model — which is exactly why the synthetic curve (unmemorizable codes) and the 715k-token repo are the
clean tests.

**Controlled confirmation — MuSiQue.** That predicts: on a benchmark Opus *can't* memorize (MuSiQue's
questions are **composed** — "who founded the company that distributed UHF" — so you must chain), even
Opus should collapse on buried evidence and orchestration should recover it. It does — opposite sign
from HotpotQA:

| gold buried (K=120) | flash bnd | flash + U | opus bnd | opus + U |
|---|:---:|:---:|:---:|:---:|
| F1 | 0.190 | 0.267 (+0.077) | **0.656** ↓ from 0.956 | **0.700** (+0.044 F1, **+0.167 EM**) |

Same model, same regime; the only variable is memorizability — and **orchestration helps even the
frontier model once it can't shortcut**. (Honest cost: when evidence *fits* one pass, the
extract→synth pipeline *hurts* hard 2-hop chaining — flash 0.782→0.379 at K=8 — so discernment routes
that to solo.) **The sharpened thesis: orchestration's value tracks the model's _bottleneck_, not its
size** — we don't claim it beats Opus everywhere, and the tables say so.

### The honest flip side — atomic benchmarks (where orchestration *can't* help, and we say so)

On single-context tasks the decompose→fan-out machinery has nothing to recover, so the only lever is
**execution** (running code). Full 4-way spectrum, weak (`flash`) vs frontier (`opus`):

| benchmark | weak | **weak + ultracode** | strong | strong + ultracode |
|---|:---:|:---:|:---:|:---:|
| **HumanEval** (code, pass@1, n=164) | 0.939 | **0.988** | 1.000 | 1.000 |
| MATH-500 (competition, n=200) | 0.900 | 0.915 | 0.990 | 0.990 |
| GSM8K (grade-school, n=200/100) | 0.980 | 0.960 | 1.000 | 1.000 |

> HumanEval's **execution-feedback self-repair** (run the tests, fix on failure) lifts flash from
> 0.939 to **0.988 — within 1.2 pts of Opus's perfect score**, cutting failures 80%. But note
> `opus+ultracode == opus` everywhere: when a pass already saturates, orchestration is a wash by
> design. Reproduce: `python bench/spectrum.py`. Detail in [`BENCHMARK_SUMMARY.md`](./BENCHMARK_SUMMARY.md).

## Install — point it at a Hermes-style agent, one command

The core package is stdlib-only and self-contained, so "installing" it into a host agent is one step:

```bash
python -m ultracode.install --agent /path/to/your-hermes-agent
#  ✓ fan-out bridge: tools/delegate_tool.py found
#  ✓ LLM bridge: agent/auxiliary_client.py found
#  ✓ vendored ultracode/ → .../your-hermes-agent/ultracode  (no third-party deps)
#  ✓ delegate_task thread-safety wired (concurrent fan-out is serialized at runtime)
#  ✓ wrote ultracode_quickstart.py
```

It validates the two bridge points, vendors the package, reports the host's `delegate_task`
thread-safety, and drops a quickstart. Then it's **one import** in your turn loop or a tool:

```python
from ultracode.integration import ultracode_run

result = ultracode_run(task, parent_agent=self, context=src)   # decompose→fan-out→verify→synthesize
print(result.answer)        # synthesized + adversarially verified
```

`ultracode_run` wires the host's own `auxiliary_client.call_llm` and a **thread-safe delegate
fan-out** (an RLock around `delegate_task`, so parallel waves can't race the host's globals — the
portable "delegate patch", applied at runtime, no source edit, idempotent). Use `--check` for a
dry-run, `--agent <path>` against either of your agents.

## Use it standalone (any backend, no host)

```python
from ultracode.harness import run

result = run(
    "Find all security bugs in this code, then write a hardened version.",
    context=source_code,
    delegate_fn=my_fanout_fn,    # runs N sub-agents in parallel, returns their results
    aux_call_fn=my_llm_call_fn,  # a single model call (planner / skeptic / synthesizer)
)
print(result.answer)             # synthesized, verified
print(result.findings)           # every finding, with survival/verdict
```

## What it actually does

Three primitives, plus the cognitive **stance** that LLMs don't apply on their own:

1. **Max reasoning effort** (xhigh).
2. **Deterministic sub-agent orchestration** — decompose, fan out, reconcile, verify.
3. **Standing behavioral injection** — an adversarial, default-to-refuted stance, first-class.

The agent **reasons out its own approach** end-to-end (`planner.plan_approach`): the shape
(solo / parallel / loop / judge-panel), the facet decomposition, what each worker produces, and
**what verification even means for this task** (a bug's data-flow? a claim's accuracy? an argument's
logic?). The hardcoded `kinds.py` defaults are *fallback only* — teach the skill in the meta-prompt,
don't script the method. (Measured: agent-driven beat a hardcoded recipe, 0.937 vs 0.867 coverage.)

### Execution as a reasoning aid
For computable work, ultracode lets the model **write and run code**, then folds the computed value
back in as *authoritative evidence* — it augments the reasoning, never short-circuits it. This is the
lever behind the benchmark headline: HumanEval's self-repair loop (write → run the official tests →
read the failure → fix) and MATH's execution-assisted arithmetic. On an internal 109-task cognitive
suite it lifts flash from **91.7% → 96.3% of Opus**. (`compute.py`)

### Discernment, not always-full-metal
A solo-first triage (`triage.py`) escalates to a light ensemble or a full loop-until-dry **only when
it would help**. A bounded, confident, low-stakes task terminates at solo — orchestration that adds
cost but not recall is the anti-pattern. This is the difference between ~1.5× and 30–80× overhead.

### The accuracy stack (false-positive machine → accurate auditor)
A weak finder + a weak verifier is a false-positive machine. Three composing gates fix it — none
sufficient alone:

| gate | mechanism | module |
|------|-----------|--------|
| **Adjudication** | full-file context + burden-of-proof: name the attacker, trace source→sink, prove no guard, prove a trust boundary is crossed | `adjudicate.py` |
| **Strong verifier** | run adjudication on a model stronger than the finders to break correlated errors | `verify.py` |
| **Execution arbiter** | a cheap model writes a repro; the runtime runs it; `exit 0` resurrects a finding the verifier over-killed | `groundtruth.py`, `execute.py` |

On 12 real findings from a production codebase: pro adjudication dropped 10/10 false positives, and
execution resurrected 2/2 reals the strong verifier over-killed → **12/12 correct**.

## When it wins (the honest regime map)

Orchestration is a **regime tool**, not a 24/7 win. It earns its cost when the work exceeds what one
focused pass can hold — and *loses* (pure overhead) when a capable model already saturates a single
pass. The benchmark spectrum above is this map, measured.

| regime | single pass | ultracode |
|--------|-------------|-----------|
| trivial recall / saturated single-pass (GSM8K, Opus-anything) | saturates | ties — *route to solo* |
| **headroom exists** (weak model on HumanEval / MATH) | leaves errors on the table | **execution + verification recover them** |
| **corpus exceeds one context window** (deep research / repo-scale audit) | sees a fraction | **chunk → fan out → union recovers all** |

Proven on real corpora (`corpus.py`): a 715k-token codebase, the single pass recovers 1 of 42
scattered classes (0.02); 286 chunk-extractors recover all 42 (1.00). Language/repo-agnostic.

**The keeper:** orchestration multiplies what the model *has* (search, breadth, verification,
computation); it can't manufacture what it *lacks* (taste). Measured cleanly — on 70 subjective
writing tasks vs Opus, ultracode is a **wash** (84% vs 87% rubric); you can't orchestrate taste.

## Layout

```
ultracode/
  harness.py      run() — the PERCEIVE→SCOPE→DECIDE→ORCHESTRATE→VERIFY→SYNTHESIZE→CRITIQUE loop
  integration.py  ultracode_run() + threadsafe_delegate() — one-call entry for a host agent
  install.py      `python -m ultracode.install --agent <path>` — vendor + wire + report
  planner.py      plan_approach() — the agent reasons out its OWN method (+ kinds.py fallback)
  steering.py     decide() — should_orchestrate / shape / loop, restraint by default
  triage.py       discernment: solo / light / full
  verify.py       adversarial skeptics — VOI-triaged, default-to-refuted, survival modes
  adjudicate.py   the accuracy gate (burden of proof)
  groundtruth.py  execute.py   execution arbiter (run a repro; resurrect over-killed reals)
  compute.py      execution as a REASONING aid — agent writes+runs code, folded in as evidence
  discovery.py    loop-until-dry; critic.py  completeness critic; judge.py  judge-panel
  pipeline.py     the NO-BARRIER reactive driver — spawn sub-agents ON THE FLY (run_reactive)
  corpus.py       repo.py      deep research / audit over a real on-disk corpus (chunk→fan-out)
  schema.py       graph.py     reconcile/dedupe (contradiction-preserving), DAG chassis, findings
  conductor.py    config.py    ledger.py   session-executive frame, knobs, run journal
  adapters.py     the optional bridge to a host runtime (else pass your own call_fn)
  DOCTRINE.md     CONTRACTS.md the operating doctrine + the contracts gate
tests/            132 tests, no live model (fakes injected)
bench/            benchmark suite. orchestration-regime: longctx_bench.py (the headline curve),
                  corpus/audit/research. atomic: gsm8k/humaneval/math + spectrum.py. key from env
```

## Tests & CI

```bash
python -m pytest tests/ -q -o addopts=""          # 132 tests, no network
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the suite on Python 3.9/3.11/3.12,
asserts the package imports with **zero third-party deps**, and dry-runs the installer against a
synthetic host on every push.

### Reproduce the benchmarks
The `bench/` suite drives a real model and reads its API key from the environment
(`DEEPSEEK_API_KEY` or `~/.ultracode-bench/deepseek.env`) — **no keys are committed**.

```bash
# the headline: the orchestration-regime scaling curve
python bench/longctx_bench.py single_budget deepseek-v4-flash     # bounded single pass (collapses)
python bench/longctx_bench.py ultracode     deepseek-v4-flash     # chunk → fan-out → reconcile (holds)
python bench/longctx_curve.py                                     # the combined curve

# the atomic spectrum (where execution helps, orchestration washes — honest context)
python bench/humaneval_bench.py ultracode deepseek-v4-flash 164   # + execution-feedback self-repair
python bench/math_bench.py      ultracode deepseek-v4-flash 200 && python bench/math_judge.py
python bench/spectrum.py                                          # the 4-way atomic table
```

Some demonstration scripts (`adjudicate_hermes.py`, `arbiter_*.py`, `corpus_real.py`, `real_task.py`)
hardcode local paths to a target checkout — illustrative, not part of the test suite; point them at
your own path.

## Integrating into a host agent

A Hermes-style agent already exposes the two primitives ultracode needs — `tools.delegate_tool.delegate_task`
(fan-out) and `agent.auxiliary_client.call_llm` (a bounded call). `install.py` vendors the package and
`integration.py` wires them; you call `ultracode_run(task, parent_agent=self)`. A reference WebUI
integration (a run-mode toggle + a live orchestration panel + a turn-level behavioral injection) lives on
the `hermes-webui` side.

---

See [`BENCHMARK_SUMMARY.md`](./BENCHMARK_SUMMARY.md) for the full arc across every benchmark, and
[`REPORT.md`](./REPORT.md) for the engineering report — including every place orchestration *didn't*
help and the fixes that made it honest.
