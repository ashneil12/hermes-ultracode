"""The third gate: execution resurrects a real finding a strong verifier over-killed.

The OAuth host-check finding (anthropic_adapter.py:376) is the hardest case in the
hermes set: the FINDER (flash) overclaims it ("token leak, high"); the ADJUDICATOR
(pro), applying burden-of-proof, judges base_url operator-controlled and marks it
false_positive — dropping a defect that is objectively real. Neither reasoning gate
gets it right alone. But the defect is *executable ground truth*: the substring
check `"anthropic.com" in host` returns True for `api.anthropic.com.evil.com`.

So we let EXECUTION arbitrate. A cheap model writes a repro; the runtime runs it;
exit 0 (substring check misclassifies the malicious host) is ground truth that
RESURRECTS the finding pro killed. This is why the stack needs all three gates:
reasoning catches most FPs, but only execution can overrule a wrong reasoning call.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.groundtruth import arbitrate_findings
from ultracode.schema import Finding, Verdict
from bench.deepseek_client import DeepSeekClient

# The real function under test (verbatim from agent/anthropic_adapter.py:365-378).
CODE = '''
def _normalize_base_url_text(base_url):
    if not base_url:
        return ""
    return str(base_url).strip()

def _is_third_party_anthropic_endpoint(base_url):
    normalized = _normalize_base_url_text(base_url)
    if not normalized:
        return False            # No base_url = direct Anthropic API
    normalized = normalized.rstrip("/").lower()
    if "anthropic.com" in normalized:
        return False            # treated as DIRECT Anthropic -> OAuth token applies
    return True                 # third-party proxy -> OAuth skipped
'''


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    # The finding exactly as pro left it: survived=False (pro said false_positive).
    f = Finding(
        claim=("Host check uses substring `\"anthropic.com\" in host`, so a malicious base_url "
               "like https://api.anthropic.com.evil.com is misclassified as DIRECT Anthropic "
               "(_is_third_party_anthropic_endpoint returns False), so OAuth applies to a non-Anthropic host."),
        locator="agent/anthropic_adapter.py:376",
        severity="high",
        evidence="substring match instead of host suffix/exact match",
    )
    f.survived = False
    f.verdict = Verdict.REFUTED   # pro killed it

    print(f"BEFORE arbiter:  survived={f.survived}  verdict={f.verdict}")
    c = DeepSeekClient(model=model, max_workers=4)
    out = arbitrate_findings([f], CODE, aux_call_fn=c.aux_call_fn)
    gt = (f.raw or {}).get("ground_truth", {})
    print(f"repro reproduced={gt.get('reproduced')}  detail={gt.get('detail')}")
    ex = gt.get("exec") or {}
    print(f"exec: exit={ex.get('returncode')}  stdout={(ex.get('stdout') or '').strip()[:200]}")
    print(f"AFTER  arbiter:  survived={f.survived}  verdict={f.verdict}  arbiter={f.raw.get('arbiter','-')}")
    print(f"counts: {out}")
    print("\nRESULT:", "RESURRECTED — execution overruled pro's false_positive"
          if out.get("resurrected") else "not resurrected (repro did not reproduce)")


if __name__ == "__main__":
    main()
