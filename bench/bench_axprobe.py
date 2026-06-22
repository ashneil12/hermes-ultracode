"""Benchmark Task 1 — find_all sweep: every place AXProbe is touched.

Runs the FULL ultracode harness (steering -> fanout -> verify -> critic ->
synthesize) on the real Notch Pal repo via the standalone DeepSeek backend, then
scores recall/precision against the CURRENT ground truth (re-derived at HEAD,
not CC's stale snapshot).

A/B: baseline (single weak-model pass) vs ultracode (full harness).
"""
import os, sys, time, glob, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# load deepseek env
envf = os.path.expanduser("~/.ultracode-bench/deepseek.env")
if os.path.exists(envf):
    for line in open(envf):
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.schema import VerifyLens
from bench.deepseek_client import DeepSeekClient

REPO = os.path.expanduser("~/Projects/Notch Pal/notchi")

# ---- current ground truth (file-level), re-derived independently ----
GROUND_TRUTH_FILES = {
    "AXProbe.swift", "RoamingController.swift",
    "AwarenessSettingsView.swift", "AXContext.swift",
}

def gather_context():
    """Pack the relevant swift files as context (the corpus to sweep)."""
    files = glob.glob(os.path.join(REPO, "**", "*.swift"), recursive=True)
    # keep it scoped + cheap: only the Awareness/Roaming/Settings + AppDelegate surface
    keep = [f for f in files if re.search(r"AXProbe|AXContext|Roaming|Awareness|AppDelegate", f)]
    blob = []
    for f in sorted(keep):
        rel = f.replace(REPO + "/", "")
        try:
            blob.append(f"\n===== FILE: {rel} =====\n" + open(f).read())
        except Exception:
            pass
    return "\n".join(blob), keep

def score(answer_text):
    found = {f for f in GROUND_TRUTH_FILES if f in (answer_text or "")}
    recall = len(found) / len(GROUND_TRUTH_FILES)
    missed = GROUND_TRUTH_FILES - found
    return recall, found, missed

def main():
    context, kept = gather_context()
    task = ("Find EVERY place the symbol `AXProbe` is touched across this codebase, "
            "including indirect coupling (a file that drives or gates AXProbe's behavior "
            "even without naming it directly). For each, give file and a one-line reason. "
            "Be exhaustive — missing a reference is the failure mode.")
    print(f"corpus: {len(kept)} swift files, {len(context)} chars")
    print(f"ground truth (files): {sorted(GROUND_TRUTH_FILES)}\n")

    # --- A: baseline single pass ---
    cb = DeepSeekClient(model="deepseek-v4-flash", max_workers=4)
    t0 = time.time()
    base = cb.chat([{"role": "user", "content": task + "\n\nCODEBASE:\n" + context}])
    base_txt = cb._content(base)
    rb, fb, mb = score(base_txt)
    ub = cb.usage.snapshot()
    print(f"[BASELINE] {time.time()-t0:.0f}s {ub['total_tokens']}tok | recall={rb:.2f} found={sorted(fb)} missed={sorted(mb)}")

    # --- B: full ultracode harness ---
    cu = DeepSeekClient(model="deepseek-v4-flash", max_workers=16)
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.COMPLETENESS],
                          max_finders=4, concurrency=16, max_children=8)
    t0 = time.time()
    res = run(task, context=context, kind="audit", delegate_fn=cu.delegate_fn,
              aux_call_fn=cu.aux_call_fn, config=cfg, force_orchestrate=True,
              run_id="axprobe", enable_ledger=False)
    ru, fu, mu = score(res.answer or "")
    uu = cu.usage.snapshot()
    print(f"[ULTRACODE] {time.time()-t0:.0f}s {uu['total_tokens']}tok | mode={res.mode} | recall={ru:.2f} found={sorted(fu)} missed={sorted(mu)}")
    print(f"  stages: {res.stages}")
    if res.findings:
        print(f"  findings: {len(res.survivors)} survived of {len(res.findings)}")
    print("\n--- ULTRACODE ANSWER (first 1200 chars) ---\n" + (res.answer or "")[:1200])

    print(f"\n{'='*70}\nSCORE: baseline recall={rb:.2f} ({ub['total_tokens']}tok) vs ultracode recall={ru:.2f} ({uu['total_tokens']}tok)")

if __name__ == "__main__":
    main()
