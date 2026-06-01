"""Does the adjudication gate convert flash's false positives into rejections?

Re-adjudicates the 12 hermes findings (with full-context + burden of proof) on
flash AND pro, and scores against Claude's ground truth (9 false-positive, 3 real).
Shows whether the STEPS fix accuracy, and how much the verifier MODEL matters.
"""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.adjudicate import adjudicate_finding
from ultracode.schema import Finding
from bench.deepseek_client import DeepSeekClient

ROOT = "/Users/ash/Projects/vanilla-hermes-agent"
# (locator, severity, claim, claude_truth)  truth: real | fp
F = [
    ("acp_adapter/server.py:387", "high", "Unvalidated URI in image block -> SSRF", "fp"),
    ("agent/agent_runtime_helpers.py:1521", "high", "Untrusted LLM tool args to internal functions, no sanitization", "fp"),
    ("agent/anthropic_adapter.py:376", "high", "OAuth token leak via substring 'anthropic.com' hostname check", "real"),
    ("agent/auxiliary_client.py:936", "high", "Thread-unsafe shared client races on self._client", "fp"),
    ("acp_adapter/permissions.py:82", "medium", "itertools.count thread-unsafe -> duplicate tool_call_id", "fp"),
    ("acp_adapter/permissions.py:83", "medium", "command/description interpolated into tool call -> injection", "fp"),
    ("acp_adapter/server.py:167", "medium", "Null byte injection in path from URI (unquote %00)", "real"),
    ("acp_adapter/server.py:385", "medium", "Unvalidated data field -> arbitrary content in data URL", "fp"),
    ("acp_adapter/server.py:769", "medium", "Untrusted env var injection in MCP server config", "fp"),
    ("acp_adapter/server.py:1912", "medium", "Missing authz: any caller can change session mode", "fp"),
    ("acp_adapter/server.py:1928", "medium", "Missing authz: any caller can set arbitrary config", "fp"),
    ("acp_adapter/session.py:614", "medium", "SSRF via attacker-controlled base_url", "fp"),
]


def window(locator):
    path, line = locator.split(":")[0], int(locator.split(":")[1])
    lines = open(f"{ROOT}/{path}", encoding="utf-8", errors="replace").read().splitlines()
    lo, hi = max(0, line - 220), min(len(lines), line + 220)
    return "\n".join(f"{lo+i+1}: {ln}" for i, ln in enumerate(lines[lo:hi]))


def run(model):
    c = DeepSeekClient(model=model, max_workers=12)
    print(f"\n{'='*92}\n### ADJUDICATION on {model}\n{'='*92}", flush=True)
    correct = 0
    fp_caught = fp_total = real_kept = real_total = 0
    for loc, sev, claim, truth in F:
        f = Finding(claim=claim, locator=loc, severity=sev)
        adj = adjudicate_finding(f, window(loc), aux_call_fn=c.aux_call_fn)
        v = adj.verdict
        kept = v in ("real", "conditional")  # conditional = real-but-gated, still kept
        agrees = (truth == "real" and kept) or (truth == "fp" and not kept)
        correct += agrees
        if truth == "fp":
            fp_total += 1; fp_caught += (not kept)
        else:
            real_total += 1; real_kept += kept
        print(f"  [{v:15}] truth={truth:4} {'OK ' if agrees else 'X  '} {loc}  sev->{adj.true_severity or '?'}", flush=True)
    print(f"\n  accuracy={correct}/{len(F)}  FP-caught={fp_caught}/{fp_total}  real-kept={real_kept}/{real_total}  "
          f"| {c.usage.snapshot()['total_tokens']}tok", flush=True)


if __name__ == "__main__":
    run("deepseek-v4-flash")
    run("deepseek-v4-pro")
