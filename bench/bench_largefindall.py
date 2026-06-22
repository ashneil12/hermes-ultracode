"""Benchmark Task 3 — LARGE corpus find-all (the regime ultracode WINS).

155 swift files / 1.26M chars — past single-pass context. Baseline MUST truncate
(structurally can't see it all). The harness's chunked corpus enumeration +
retry-empty should recover references the truncated baseline misses.

Target: every file referencing `AppSettings` (ground truth via grep = 22 files).
Score: file-level recall. This is the attention-dilution / needle-in-haystack
regime from ULTRACODE_REPORT — the one the gate now correctly escalates to.
"""
import os, sys, time, glob, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

envf = os.path.expanduser("~/.ultracode-bench/deepseek.env")
if os.path.exists(envf):
    for line in open(envf):
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1); os.environ.setdefault(k, v)

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient

REPO = os.path.expanduser("~/Projects/Notch Pal/notchi")
SYMBOL = "AppSettings"

def ground_truth():
    files = glob.glob(os.path.join(REPO, "**", "*.swift"), recursive=True)
    gt = set()
    for f in files:
        try:
            if SYMBOL in open(f).read():
                gt.add(os.path.basename(f))
        except Exception:
            pass
    return gt

def build_corpus():
    files = sorted(glob.glob(os.path.join(REPO, "**", "*.swift"), recursive=True))
    blob = []
    for f in files:
        rel = f.replace(REPO + "/", "")
        try:
            blob.append(f"\n===== FILE: {rel} =====\n" + open(f).read())
        except Exception:
            pass
    return "\n".join(blob)

def score(answer, gt):
    a = (answer or "")
    found = {fn for fn in gt if fn in a}
    return len(found) / len(gt), found, (gt - found)

def main():
    gt = ground_truth()
    corpus = build_corpus()
    print(f"corpus: {len(corpus)} chars | ground truth: {len(gt)} files reference {SYMBOL}\n")
    task = (f"Find EVERY file that references the symbol `{SYMBOL}` in this codebase. "
            f"List each filename. Be exhaustive — the corpus is large, missing a file is the failure.")

    # BASELINE — single pass, MUST truncate a 1.26M corpus to fit context
    cb = DeepSeekClient(model="deepseek-v4-flash", max_workers=4)
    t0 = time.time()
    # simulate the real single-shot limit: a baseline can't send 1.26M tokens; truncate.
    truncated = corpus[:120000]  # ~30k tokens, a generous single-shot window
    base = cb._content(cb.chat([{"role":"user","content": task + "\n\nCODEBASE (may be truncated):\n" + truncated}]))
    rb, fb, mb = score(base, gt)
    ub = cb.usage.snapshot()
    print(f"[BASELINE single-pass, corpus truncated to 120k]  {time.time()-t0:.0f}s {ub['total_tokens']}tok | recall={rb:.2f} ({len(fb)}/{len(gt)})")

    # ULTRACODE — chunked enumerate-corpus over the FULL 1.26M
    cu = DeepSeekClient(model="deepseek-v4-flash", max_workers=16)
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.COMPLETENESS],
                          max_finders=8, concurrency=16, max_children=8)
    t0 = time.time()
    res = run(task, context=corpus, kind="audit", delegate_fn=cu.delegate_fn,
              aux_call_fn=cu.aux_call_fn, config=cfg, force_orchestrate=True,
              run_id="largefindall", enable_ledger=False)
    ru, fu, mu = score(res.answer or "", gt)
    uu = cu.usage.snapshot()
    print(f"[ULTRACODE chunked over full 1.26M]  {time.time()-t0:.0f}s {uu['total_tokens']}tok | recall={ru:.2f} ({len(fu)}/{len(gt)})")
    print(f"  stages: {res.stages}")
    print(f"\n{'='*70}\nSCORE  baseline recall={rb:.2f}  vs  ultracode recall={ru:.2f}")
    print("ULTRACODE WINS" if ru > rb + 0.05 else ("TIE" if abs(ru-rb)<=0.05 else "baseline wins"))
    if mu: print(f"ultracode still missed: {sorted(mu)[:10]}")

if __name__ == "__main__":
    main()
