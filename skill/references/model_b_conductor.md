# Model B — the agent as conductor (the live, in-session execution path)

The harness's Python run() can't reach the agent's TaskDelegate (a subprocess
can't call back up into the agent's turn). So LIVE ultracode runs Model B: the
AGENT is the conductor. Pure-Python harness modules supply JUDGMENT; the agent
supplies the FAN-OUT via its own parallel-subagent tool.

## Recipe: live find-all / exhaustive sweep (validated on clawsweeper ghJson, 120 files)

1. Ground-truth the answer key first (for a verifiable target): a plain
   `grep -rl` gives the set to score against. For real unknown sweeps, skip this.
2. Chunk the corpus into N sections (one group of files per intended subagent),
   write each to a temp file. Keep any single chunk readable in one subagent pass.
3. Fan out with TaskDelegate (role=orchestrator, N leaf tasks), one per chunk.
   Each leaf: "list every file referencing X, one per line, NONE if none, read the
   WHOLE file." Different chunk per child; tell the large-chunk child explicitly not
   to stop early (the silent-truncation failure mode).
   **PIN AN UNAMBIGUOUS MATCH RULE, identical for every worker** (validated lesson,
   clawsweeper ghJson run): state EXACTLY what counts — e.g. "exact identifier `foo`
   only" vs "any substring `foo` incl. `fooWithRetry`". An ambiguous rule makes
   workers disagree (some include variants, some don't) and silently caps recall.
   This is the contract-drift failure-lens; the spec is the weakest link in a sweep.
4. Union + dedup the returned file-lists (case/path-insensitive).
5. Retry the holes — any chunk that returned empty/errored gets re-dispatched
   ONCE (the retry_empty discipline; a token-starved chunk must not silently cap recall).
6. Score / report lead-first, with the count and any residual uncertainty.

## Recipe: live adversarial review

1. Recon solo: read the target, draft the candidate findings yourself.
2. Fan out finders with DIFFERENT framings (one per failure-lens) via TaskDelegate.
3. Union + dedup findings (merge near-duplicates; count agreement).
4. Verify: re-dispatch survivors to FRESH skeptic leaves, give them the SOURCES
   not the finders' reasoning, instruct "default to refuted; a value safe given its
   CALLERS is NOT a bug; state a concrete exploitation path or refute." (Benchmark:
   this kills the context-safe decoys a single pass flags.)
5. Synthesize solo: lead with killed-and-confirmed, minority report for the rest.

## The judgment helpers (pure Python, import anywhere, zero runtime)

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/Projects/hermes-ultracode"))
from ultracode.steering import decide              # orchestrate vs solo + shape
from ultracode.schema import Finding, dedupe_findings, reconcile_findings
# dedupe_findings: merges identical claims, sets agreement_count
# reconcile_findings: root-cause dedup (near-duplicate, polarity-aware)
```

## When to use Model A instead (the bench backend)

Reproducible benchmarking / measuring the engine in isolation: run
harness.run(..., delegate_fn=DeepSeekClient(...).delegate_fn, ...) in-process.
Not for live user work (its children aren't the live agent), but it's the honest
way to A/B the engine vs a baseline.
