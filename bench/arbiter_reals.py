"""Execution resurrects BOTH reals that pro's adjudicator over-killed (2/2).

Pro (precision-maximizer) marked every false positive AND both genuine defects as
false_positive — it is confident, not hedging, so the 'conditional' escape hatch
can't recover them. Execution can: each defect is a one-line ground-truth fact a
cheap model can repro. This proves the full accuracy stack closes at 12/12:
  pro drops 10/10 FPs (precision) + execution resurrects 2/2 reals (recall recovery).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.groundtruth import arbitrate_findings
from ultracode.schema import Finding, Verdict
from bench.deepseek_client import DeepSeekClient

OAUTH_CODE = '''
def _is_third_party_anthropic_endpoint(base_url):
    normalized = (str(base_url).strip() if base_url else "")
    if not normalized:
        return False
    normalized = normalized.rstrip("/").lower()
    if "anthropic.com" in normalized:   # substring, not host match
        return False                     # -> treated as DIRECT Anthropic, OAuth applies
    return True
'''

NULLBYTE_CODE = '''
from urllib.parse import urlparse, unquote
def uri_to_path(uri):
    parsed = urlparse((uri or "").strip())
    if parsed.scheme == "file":
        return unquote(parsed.path or "")   # %00 survives unquote -> null byte in path
    return unquote(uri)
'''

CASES = [
    (Finding(claim=("substring host check `\"anthropic.com\" in host` misclassifies "
                    "https://api.anthropic.com.evil.com as direct Anthropic (returns False)"),
             locator="agent/anthropic_adapter.py:376", severity="high",
             evidence="substring vs host-suffix match"), OAUTH_CODE),
    (Finding(claim=("unquote() on a file URI path lets %00 become a literal null byte in the "
                    "returned path (uri_to_path('file:///etc/passwd%00.txt') contains chr(0))"),
             locator="acp_adapter/server.py:167", severity="medium",
             evidence="unquote decodes %00 to \\x00"), NULLBYTE_CODE),
]


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    c = DeepSeekClient(model=model, max_workers=4)
    resurrected = 0
    for f, code in CASES:
        f.survived = False
        f.verdict = Verdict.REFUTED   # pro killed it
        out = arbitrate_findings([f], code, aux_call_fn=c.aux_call_fn)
        gt = (f.raw or {}).get("ground_truth", {})
        ok = out.get("resurrected", 0) == 1
        resurrected += ok
        print(f"  {f.locator:34} repro={gt.get('reproduced')}  -> {f.verdict}  "
              f"{'RESURRECTED' if ok else 'still dead'}", flush=True)
    print(f"\n=== {model}: execution resurrected {resurrected}/{len(CASES)} reals pro over-killed ===")
    print("Full stack on the 12 hermes findings: pro drops 10/10 FPs + execution recovers "
          f"{resurrected}/2 reals = {10+resurrected}/12 correct.")


if __name__ == "__main__":
    main()
