# hermes-ultracode

A deterministic **orchestration harness** that makes a weak model punch above its weight on hard
tasks — by wrapping it in *decompose → fan-out → adversarially verify → synthesize*, and by
**reasoning out its own method** rather than following a hardcoded recipe.

Ported from the "ultracode" mode of Claude Code into a self-contained, runtime-agnostic Python
package. It drives any backend you give it (a frontier model, a local model, or a cheap/weak one)
via two injected callables — there are **no third-party dependencies**, only the standard library.

```python
from ultracode.harness import run

result = run(
    "Find all security bugs in this code, then write a hardened version.",
    context=source_code,
    delegate_fn=my_fanout_fn,    # runs N sub-agents in parallel, returns their results
    aux_call_fn=my_llm_call_fn,  # a single model call (planner / skeptic / synthesizer)
)
print(result.answer)            # synthesized, verified
print(result.findings)          # every finding, with survival/verdict
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
pass.

| regime | single pass | ultracode |
|--------|-------------|-----------|
| trivial recall / known-topic coverage | saturates | ties (route to solo) |
| **corpus exceeds one context window** (deep research / repo-scale audit) | sees a fraction | **chunk → fan out → union recovers all** |

Proven on real corpora (`corpus.py`): a 715k-token codebase, the single pass recovers 1 of 42
scattered classes (0.02); 286 chunk-extractors recover all 42 (1.00). Language/repo-agnostic.

## Layout

```
ultracode/
  harness.py      run() — the PERCEIVE→SCOPE→DECIDE→ORCHESTRATE→VERIFY→SYNTHESIZE→CRITIQUE loop
  planner.py      plan_approach() — the agent reasons out its OWN method (+ kinds.py fallback)
  steering.py     decide() — should_orchestrate / shape / loop, restraint by default
  triage.py       discernment: solo / light / full
  verify.py       adversarial skeptics — VOI-triaged, default-to-refuted, survival modes
  adjudicate.py   the accuracy gate (burden of proof)
  groundtruth.py  execute.py   execution arbiter (run a repro; resurrect over-killed reals)
  discovery.py    loop-until-dry; critic.py  completeness critic; judge.py  judge-panel
  pipeline.py     the NO-BARRIER reactive driver — spawn sub-agents ON THE FLY as results
                  come back (run_reactive); no-barrier DAG execution (drive_graph)
  corpus.py       repo.py      deep research / audit over a real on-disk corpus (chunk→fan-out)
  schema.py       graph.py     reconcile/dedupe (contradiction-preserving), DAG chassis, findings model
  conductor.py    config.py    ledger.py   session-executive frame, knobs, run journal
  adapters.py     the only optional bridge to a host runtime (else pass your own call_fn)
  DOCTRINE.md     CONTRACTS.md the operating doctrine + the contracts gate
tests/            119 tests, no live model (fakes injected)
bench/            the benchmark suite (code audit + research + corpus); reads its key from env
REPORT.md         the full, honest engineering report — what works, what doesn't, and why
```

## Tests & benchmarks

```bash
python -m pytest tests/ -q -o addopts=""          # 119 tests, no network
```

The `bench/` suite drives a real model. It reads its API key from the environment
(`DEEPSEEK_API_KEY` or `~/.ultracode-bench/deepseek.env`) — **no keys are committed**. Some
demonstration scripts (`adjudicate_hermes.py`, `arbiter_*.py`, `corpus_real.py`,
`corpus_openclaw.py`, `real_task.py`) hardcode local absolute paths to a target codebase
checkout — they are illustrative, not part of the test suite; point them at your own path.

## Integrating into a host agent

`adapters.py` has one optional lazy bridge (`agent.auxiliary_client.call_llm`) for embedding inside a
Hermes-style agent; when absent it's ignored and the dependency-injected `call_fn`/`delegate_fn` path
is used. A reference WebUI integration (a run-mode toggle + a live orchestration panel + a turn-level
behavioral injection) lives on the `hermes-webui` side.

---

See [`REPORT.md`](./REPORT.md) for the full benchmarked findings, including every place orchestration
*didn't* help and the fixes that made it honest.
