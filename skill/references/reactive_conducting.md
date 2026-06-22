# Reactive conducting — approximating no-barrier streaming in Model B

The harness has `pipeline.run_reactive()` (true no-barrier: spawn the instant ANY
worker returns). Model B (the live agent) CAN'T do that mid-wave — `delegate_task`
returns the whole batch at once, not per-completion. So the live agent approximates
it with **small reactive waves** instead of one big barrier wave.

## The pattern (what I actually do live)

Instead of: dispatch 30 → wait for all 30 → decide (pure barrier),
do: dispatch a SMALL seed wave → read results → let findings SPAWN the next wave →
repeat until dry. Each wave's results steer the next. That's reactive *between waves*,
the achievable slice of "agent #3 found something surprising, chase it."

```
WAVE 1 (seed, cheap recon):  3-6 scouts on the highest-signal slices
   ↓ results return as a batch
REACT:  did anything surface a NEW lead the seeds didn't cover?
   - a finding points at an unscanned module      -> spawn finders there
   - a chunk came back empty/errored              -> retry just that hole
   - a finding looks load-bearing + contested     -> spawn skeptics on it NOW
   ↓
WAVE 2 (emergent, derived from wave 1, NOT pre-planned)
   ↓ ... loop until a wave adds nothing new (loop-until-dry) ...
SYNTHESIZE solo.
```

## When to use small-reactive-waves vs one big barrier wave

- **Known, uniform split** (e.g. "scan these 154 files for X") -> one barrier wave is
  fine and cheaper; there's nothing to react to, every unit is the same job.
- **Unknown/branching surface** (debugging, "trace this", research where one find
  opens three new questions) -> small reactive waves; the value IS the branching.

That distinction is the doctrine: react when results change the work-list, barrier
when they don't.

## Heavy jobs: hand the true-reactive driver the wheel

For a genuinely large branching job, the strongest move is to let the harness's real
`pipeline.run_reactive()` drive a concurrency-safe backend (the deepseek bench client),
which gives true per-completion spawning — then read the final result back. That's
Model A's reactive path; use it when the branching is deep enough that wave-granularity
isn't fine enough. For everyday live work, small reactive waves are the right tool.
