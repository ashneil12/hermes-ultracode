"""Isolated precision fix test — does a CONTEXT-AWARE skeptic kill the decoys?

Cheap (~few k tokens): feed the 2 false-positive findings + the corpus to
verify_findings with (a) the default skeptic vs (b) a caller-context-aware
skeptic. If (b) refutes the decoys while (a) lets them survive, that's the fix.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
envf=os.path.expanduser("~/.ultracode-bench/deepseek.env")
for line in open(envf):
    if '=' in line and not line.startswith('#'):
        k,v=line.strip().split('=',1); os.environ.setdefault(k,v)

from ultracode.config import UltracodeConfig
from ultracode.schema import Finding, VerifyLens
from ultracode.verify import verify_findings
from bench.deepseek_client import DeepSeekClient

CORPUS = open(Path(__file__).parent / "_review2_corpus.txt").read() if (Path(__file__).parent/"_review2_corpus.txt").exists() else ""

# The 2 decoys that wrongly survived, as findings:
decoy_findings = [
    Finding(claim="cache_key uses weak/insecure hashing for the cache key", locator="cache.py:cache_key", source_label="finder"),
    Finding(claim="current_user returns None with no auth check, allowing unauthenticated access", locator="auth.py:current_user", source_label="finder"),
]

DEFAULT = "Does this bug actually hold? State the mechanism / data-flow. If you cannot, refute it."
CONTEXT_AWARE = ("Does this bug actually hold AND is it exploitable GIVEN HOW ITS CALLERS USE IT? "
                 "Trace the data flow from every caller. A value that looks unsafe locally but is "
                 "clamped, validated, guarded by a decorator, or only ever used in a non-security "
                 "context by every caller is NOT a real bug — REFUTE it. Default to refuted unless "
                 "you can state a concrete exploitation path that survives the caller context.")

def run_verify(directive, label):
    c=DeepSeekClient(model="deepseek-v4-flash",max_workers=8)
    cfg=UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS,VerifyLens.SECURITY],
                        verify_quorum=2, verify_default_refuted=True)
    # fresh copies
    fs=[Finding(claim=f.claim, locator=f.locator, source_label="finder") for f in decoy_findings]
    out=verify_findings(fs, context=CORPUS, delegate_fn=c.delegate_fn,
                        config=cfg, skeptic_directive=directive)
    survived=[f for f in out if getattr(f,'survived',True) and (not f.verdict or f.verdict.value!='refuted')]
    u=c.usage.snapshot()
    print(f"[{label}] {u['total_tokens']}tok | decoys surviving: {len(survived)}/2")
    for f in out:
        v=f.verdict.value if f.verdict else '?'
        print(f"    {f.locator}: verdict={v}")
    return len(survived)

# need the corpus
if not CORPUS:
    print("writing corpus file from bench_review2..."); 
    import importlib.util
    spec=importlib.util.spec_from_file_location("r2", Path(__file__).parent/"bench_review2.py")
    r2=importlib.util.module_from_spec(spec); spec.loader.exec_module(r2)
    open(Path(__file__).parent/"_review2_corpus.txt","w").write(r2.CORPUS)
    globals()['CORPUS']=r2.CORPUS

print("Testing whether a context-aware skeptic kills the 2 false positives:\n")
a=run_verify(DEFAULT, "DEFAULT skeptic")
print()
b=run_verify(CONTEXT_AWARE, "CONTEXT-AWARE skeptic")
print(f"\n{'='*60}")
print(f"default let {a}/2 decoys survive; context-aware let {b}/2 survive")
print(">>> FIX CONFIRMED" if b < a else ">>> no improvement from directive alone")
