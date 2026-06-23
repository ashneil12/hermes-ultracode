# False-negative defense (the other half — what a clean "NONE" hides)

The verify pass kills false POSITIVES. It does NOTHING for false NEGATIVES — a real
issue no finder flagged. You cannot refute a claim that was never made. This is the
MORE dangerous failure, and a naive fan-out is full of it. Proven live: a 30-finder
sweep of the Hermes repo returned "26 chunks clean" but a deterministic scan then
found a `shell=True` sink (`hermes_cli/tools_config.py:822`) NO finder named, plus
whole sink classes (pickle.load, yaml.load, __import__) that were never even scoped.

## The three false-negative sources (all real, all seen)

1. **Scoping blindness.** Pre-filtering to `subprocess|shell|eval|exec` never sends
   `pickle.loads`, `yaml.load`, `__import__`, deserialization, template-injection, or
   aliased sinks to any finder. The filter IS a false-negative generator.
2. **Chunk-split blindness.** Splitting ONE file across multiple finder chunks hides
   code at the seams (the tools_config.py:822 miss — the file was in 3 chunks).
   Cross-file taint (input in A → sink in B) is invisible to per-chunk finders.
3. **Finder laziness/hallucination.** "NONE" from a model is a CLAIM, not truth. The
   same model that invents line numbers also skips real ones. Empty = UNKNOWN, not clean.

## The defense (do these, not just fan-out + verify)

1. **Deterministic ground-truth FIRST.** Before/alongside the LLM fan-out, run a
   grep/AST scan for the FULL sink-class list to get a denominator that can't
   hallucinate or get bored. Then CROSS-CHECK the fan-out's findings against it: any
   ground-truth hit no finder named is a false-negative candidate → send it to a
   fresh finder. (This is `ground-truth-once` applied to coverage, not just to a claim.)
2. **Chunk on FILE boundaries, never split a file.** One file = one finder's full view
   (or, for a huge file, give that finder the whole file and tell it not to stop early).
3. **Scope the sink list COMPLETELY.** For a security sweep that's at minimum:
   subprocess/Popen/check_output/check_call, shell=True, create_subprocess_shell,
   os.system/os.popen/os.exec*, eval/exec/compile, __import__, pickle.load(s),
   yaml.load (non-safe), marshal, and template/format-into-command.
4. **Run the completeness critic + loop-until-dry.** A from-scratch "what's MISSING"
   pass that treats its own empty result as UNKNOWN, then re-spawn discovery until K
   rounds add nothing. One round is the most false-negative-prone thing possible.
5. **Report coverage honestly.** "Scanned N files, M sink-class hits, all cross-checked"
   beats "looks clean." Name the residual unknowns; never imply absence = safety.

## The honest framing for any sweep result
A clean result is "no issue found in the scanned surface with the scoped patterns,"
NOT "this is safe." State the surface and the patterns so the gap is visible. The
deterministic denominator is what turns a vibe into an accountable coverage claim.

## PROOF: tool-using finder vs eyeballing finder (same codebase, measured)
Same task (shell/exec sink audit of vanilla-hermes-agent), two methods:

| | Original 30 finders (read text blobs) | 1 finder w/ FINDER persona (grep-first) |
|---|---|---|
| line numbers | FABRICATED (voice_mode.py:1589 doesn't exist) | all real (from grep) |
| tools_config.py:822 | MISSED (false negative) | found, correctly judged safe |
| denominator | none ("26 chunks clean") | 23 sink call-sites, 7 dangerous / 16 safe |
| time/cost | 30 agents, 158s | 1 agent, 131s |

Conclusion: the subagents always HAD grep (leaf agents inherit terminal). The
eyeballing dispatch made them hallucinate + miss. The fix is the persona, not more
agents. One grep-grounded finder beat 30 eyeballing ones on accuracy AND recall.
This is the whole case for subagent_personas.md (inject the FINDER persona via context).

## The real tool (not just prose)

`scripts/ground_truth_scan.py` is the binding version of defense #1-3. AST-based
(walks the Python AST, so regex-STRING detector patterns in approval.py /
security-guidance are NOT flagged — the AST distinguishes a string literal from a
Call node). Proven on the Hermes repo: catches the tools_config.py:822 sink the
LLM fan-out missed, and the full sink-class spread (pickle/yaml/import/shell).

Cross-check mode turns a fan-out result into an accountable coverage claim:
  python3 scripts/ground_truth_scan.py <repo> --findings fanout.md --crosscheck
prints every ground-truth sink NO finder named = false-negative candidates. The
denominator (24 on Hermes) is the number that makes "looks clean" falsifiable.

Honest limitation: the scanner is a DENOMINATOR, not a vuln oracle. It classifies
sink classes and gives the verify pass a complete work-list. It now distinguishes
common safe YAML patterns (`SafeLoader`/`CSafeLoader`) and downgrades ruamel
round-trip loaders to `yaml.load (ruamel/verify-loader)`, but each hit is still a
sink to triage, not an automatic vulnerability. Never report the raw scanner count
as "N vulnerabilities" — it's "N sinks to triage."
