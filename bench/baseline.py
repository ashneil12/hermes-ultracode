"""Baseline: the raw weak model, single shot, no harness.

This is what ultracode must beat — deepseek-v4-pro answering the same task in one
call with no decomposition, no fan-out, no adversarial verification. The fair
comparison for "does the orchestration add value over the bare model."
"""

from typing import List

from ultracode.adapters import extract_json
from ultracode.schema import Finding


def baseline_find(client, task) -> List[Finding]:
    messages = [
        {"role": "system", "content": "You are an expert code auditor. Be thorough and precise."},
        {"role": "user", "content": (
            f"{task.prompt}\n\nCODE:\n{task.code}\n\n"
            'Reply with ONLY JSON: {"findings":[{"claim":"<specific>","locator":"<line/section>",'
            '"evidence":"<why>","severity":"info|low|medium|high|critical"}]}.'
        )},
    ]
    out = client.chat(messages, temperature=0.4, max_tokens=4000)
    # client.chat returns an OpenAI response OBJECT (not a dict) — use the client's
    # own content extractor so this can't drift from the client's response shape.
    text = type(client)._content(out)
    parsed = extract_json(text)
    items = parsed.get("findings", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
    findings: List[Finding] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("claim", "")).strip():
            try:
                findings.append(Finding(
                    claim=str(it["claim"]).strip(),
                    locator=str(it.get("locator", "")).strip(),
                    evidence=str(it.get("evidence", "")).strip(),
                    severity=str(it.get("severity", "info")).strip() or "info",
                ).validate())
            except ValueError:
                continue
    return findings
