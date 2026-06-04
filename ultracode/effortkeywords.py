"""Inline reasoning-boost keywords (à la Claude Code's ``ultrathink``).

Typing a keyword like ``ultrathink`` / ``think harder`` / ``megathink`` anywhere in a message bumps
the reasoning effort for that ONE turn, then reverts. The keyword is stripped before the text reaches
the model. Whole-word, case-insensitive; multiple keywords resolve to the HIGHEST; the bump is
upward-only (a keyword never lowers the session effort — that's the caller's job, see ``resolve``).

Provider-agnostic and dependency-free: it only maps words to effort-level strings; wiring the bump for
a turn is ``reasoning.effort_scope(agent, level)``.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from ultracode.reasoning import valid_levels

# keyword -> target effort level. Longer phrases must be tried before their substrings, so order them
# by descending word count when matching (handled in _PATTERNS).
_KEYWORDS = {
    "ultrathink": "xhigh",
    "megathink": "xhigh",
    "think harder": "high",
    "think hard": "high",
    "think deeply": "high",
    "think more": "high",
}

# whole-word, case-insensitive patterns, longest phrase first so "think harder" wins over "think".
# Inter-word gaps are \s+ (not a literal space) so "think  hard" / "think\nhard" still match.
def _phrase_pattern(k: str) -> "re.Pattern":
    return re.compile(r"\b" + r"\s+".join(re.escape(w) for w in k.split()) + r"\b", re.IGNORECASE)


_PATTERNS = sorted(
    ((_phrase_pattern(k), v) for k, v in _KEYWORDS.items()),
    key=lambda kv: -len(kv[0].pattern),
)


def _rank(level: str) -> Optional[int]:
    """Rank of an effort level in the provider's ordering (higher = more effort). None if the level
    isn't a recognized level — the caller decides what unknown means (see ``resolve``)."""
    levels = [str(x).strip().lower() for x in valid_levels()]
    ll = str(level).strip().lower()
    return levels.index(ll) if ll in levels else None


def parse_effort_keywords(text: str) -> Tuple[str, Optional[str]]:
    """Return ``(cleaned_text, effort_level | None)``.

    Detects every boost keyword, resolves to the HIGHEST effort among them, strips ALL of them from
    the text, and returns the cleaned text (whitespace-collapsed). ``None`` effort means no keyword
    was present. A message that is ONLY a keyword returns ``("", level)`` — the caller decides whether
    a contentless boost is a no-op.
    """
    if not text or not isinstance(text, str):
        return text or "", None
    best: Optional[str] = None
    cleaned = text
    for pat, level in _PATTERNS:
        if pat.search(cleaned):
            cleaned = pat.sub(" ", cleaned)
            # keyword levels are canonical (always rank); -1 fallback is defensive only
            if best is None or (_rank(level) or -1) > (_rank(best) or -1):
                best = level
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, best


def resolve(text: str, session_effort: str) -> Tuple[str, str, bool]:
    """Convenience: returns ``(cleaned_text, effective_effort, bumped)``. UPWARD-ONLY — a keyword that
    resolves at-or-below the session effort is ignored (effective stays at session_effort). An
    UNRECOGNIZED ``session_effort`` can't be ranked, so we apply the bump (ultracode bias: up)."""
    cleaned, kw = parse_effort_keywords(text)
    if kw is None:
        return cleaned, session_effort, False
    kr, sr = _rank(kw), _rank(session_effort)
    if sr is not None and kr is not None and kr <= sr:
        return cleaned, session_effort, False   # keyword doesn't out-rank a known session effort
    return cleaned, kw, True
