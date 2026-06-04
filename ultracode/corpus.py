"""corpus.py — parallel DEEP RESEARCH over a real on-disk corpus.

The research analog of repo.py's chunked audit: chunk real documents, fan out one
EXTRACTOR per chunk (each READS its chunk and pulls out what is relevant to the
question), reconcile, optionally verify, then landscape-synthesize. This is the regime
where orchestration beats a single pass — when the corpus exceeds one context window, a
truncated single pass structurally cannot see the tail, while chunked focused reads
recover all of it (and each chunk gets full attention, not lost-in-the-middle).

Two modes:
  - exhaustive find-all: read EVERY chunk (coverage scales linearly with the corpus).
  - focused (retrieval): rank chunks by relevance to the question, read the top-K, and
    ANNOUNCE what was skipped — never a silent cap.

Reuses repo.chunk_repo (real file reading + chunking), delegate_fanout (the proven
concurrent wave dispatch), reconcile_findings (now contradiction-preserving), the
adversarial verifier, and harness._synthesize in landscape mode.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ultracode.adapters import delegate_fanout, extract_json
from ultracode.config import UltracodeConfig
from ultracode.repo import Chunk, chunk_repo
from ultracode.schema import Finding, dedupe_findings, reconcile_findings
from ultracode.verify import survivors as _survivors, verify_findings


@dataclass
class CorpusResearchResult:
    question: str = ""
    answer: str = ""
    n_files: int = 0
    n_chunks: int = 0
    chunks_read: int = 0
    findings: List[Finding] = field(default_factory=list)
    caps_announced: List[str] = field(default_factory=list)


# Above this finding count, the single-call prose synthesis condenses lossily, so the
# complete deduped union is appended as the authoritative deliverable (announced).
_LOSSY_SYNTH_AT = 40

_TOK = re.compile(r"[a-z0-9_]+")
_QSTOP = set(
    "the a an is are be of to in on for and or with what which list every all each that this it does "
    "do how who when where why their them they name names defined definition note one line".split()
)


def _keywords(text: str) -> set:
    return {w for w in _TOK.findall((text or "").lower()) if len(w) > 2 and w not in _QSTOP}


def relevance_rank(chunks: List[Chunk], question: str) -> List[Chunk]:
    """Cheap retrieval: rank chunks by keyword overlap with the question. Used to read
    the most-relevant top-K for a FOCUSED question (exhaustive find-all reads all)."""
    qk = _keywords(question)
    return sorted(chunks, key=lambda c: -len(qk & _keywords(c.text)))


def _extract_prompt(question: str, chunk: Chunk) -> str:
    return (
        "You are a research analyst reading ONE section of a larger corpus. Extract from THIS section "
        "everything relevant to the question — and ONLY what is actually present here.\n\n"
        f"QUESTION: {question}\n\n"
        f"SECTION ({chunk.path}, lines {chunk.start}+; line numbers are prefixed):\n{chunk.text}\n\n"
        "Quote SPECIFICS verbatim (names, identifiers, definitions, values, signatures). Do NOT infer beyond "
        "the text; do NOT invent items not in this section.\n"
        'Reply with ONLY JSON: {"findings":[{"claim":"<the specific item + what it is>",'
        '"locator":"<path:line or section>","evidence":"<the supporting text>","severity":"info"}]}. '
        'Return {"findings":[]} if nothing in this section is relevant.'
    )


def _parse(entry, chunk: Chunk) -> List[Finding]:
    if not isinstance(entry, dict) or entry.get("status") != "completed":
        return []
    parsed = extract_json(entry.get("summary") or "")
    items = parsed.get("findings", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
    out: List[Finding] = []
    for it in items:
        if isinstance(it, dict) and str(it.get("claim", "")).strip():
            loc = str(it.get("locator") or chunk.path).strip() or chunk.path
            try:
                out.append(Finding(
                    claim=str(it["claim"]).strip(), locator=loc,
                    evidence=str(it.get("evidence", "")).strip(),
                    severity=str(it.get("severity", "info")).strip() or "info",
                    source_label=chunk.path,
                ).validate())
            except ValueError:
                continue
    return out


def research_corpus(
    root: str,
    question: str,
    *,
    ext=(".py", ".md", ".txt", ".rst"),
    delegate_fn: Optional[Callable[..., str]] = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    config: Optional[UltracodeConfig] = None,
    agent: Any = None,
    model: Optional[str] = None,
    max_files: Optional[int] = None,
    max_chunk_lines: int = 300,
    top_k_chunks: Optional[int] = None,
    concurrency: int = 24,
    retry_empty: int = 1,
    single_pass_chars: int = 0,
    verify: bool = False,
    synthesize: bool = True,
    progress: Optional[Callable[[str], None]] = None,
    **chunk_kw,
) -> CorpusResearchResult:
    """Deep-research over a real corpus: chunk -> fan out one reader/extractor per chunk
    -> reconcile -> (verify) -> landscape synthesize. Cost is linear in chunks read."""
    cfg = config or UltracodeConfig()
    chunks = chunk_repo(root, ext=ext, max_chunk_lines=max_chunk_lines, max_files=max_files, **chunk_kw)
    res = CorpusResearchResult(question=question, n_files=len({c.path for c in chunks}), n_chunks=len(chunks))
    if not chunks:
        res.caps_announced.append(
            f"no readable documents found under {root} matching ext={ext} "
            f"(check the ext filter, min_file_lines, include/exclude, or permissions)")
        return res

    if top_k_chunks and len(chunks) > top_k_chunks:
        ranked = relevance_rank(chunks, question)
        skipped = len(chunks) - top_k_chunks
        chunks = ranked[:top_k_chunks]
        res.caps_announced.append(
            f"retrieval: read top {top_k_chunks} of {res.n_chunks} chunks by relevance; "
            f"{skipped} lower-relevance chunks skipped (ANNOUNCED, not silent)")
    # FITS-ONE-PASS GUARD: when the whole (post-retrieval) corpus fits a single read, do ONE
    # combined extraction instead of fanning out. Chunking fragments evidence that must be CHAINED
    # across sections (multi-hop), so the union of per-chunk reads underperforms a direct read when
    # there's no coverage pressure — discernment at the corpus level. Opt-in (0 = always fan out).
    if single_pass_chars and sum(len(c.text) for c in chunks) <= single_pass_chars:
        chunks = [Chunk(path="<combined>", start=1, text="\n\n".join(c.text for c in chunks))]
        res.caps_announced.append(
            "single-pass: corpus fits one read; combined extraction (no cross-section fragmentation)")
    res.chunks_read = len(chunks)
    if progress:
        progress(f"extracting from {len(chunks)} chunks / {res.n_files} files (concurrency {concurrency})")

    tasks = [{"goal": _extract_prompt(question, c)} for c in chunks]
    results = delegate_fanout(tasks, parent_agent=agent, max_children=cfg.max_children,
                              concurrency=concurrency, delegate_fn=delegate_fn, retry_empty=retry_empty)
    raw: List[Finding] = []
    for i, entry in enumerate(results):
        raw.extend(_parse(entry if isinstance(entry, dict) else {}, chunks[i % len(chunks)]))
    res.caps_announced.append(f"extracted {len(raw)} items from {len(chunks)} chunks across {res.n_files} files")

    findings = reconcile_findings(raw) if cfg.reconcile else dedupe_findings(raw)
    if len(raw) != len(findings):
        res.caps_announced.append(f"reconciled {len(raw)} -> {len(findings)} (merged duplicates; contradictions kept)")
    res.findings = findings

    survs = findings
    if verify and findings:
        verify_findings(findings, parent_agent=agent, config=cfg, lenses=cfg.verify_lenses,
                        delegate_fn=delegate_fn, concurrency=concurrency)
        survs = _survivors(findings)
        res.caps_announced.append(f"verified: {len(survs)}/{len(findings)} survived")

    if synthesize and aux_call_fn:
        from ultracode.harness import _synthesize
        res.answer = _synthesize(question, survs, findings, crit_note="", model=model, rt=None,
                                 aux_call_fn=aux_call_fn, landscape=True)
        # The prose landscape synth is KNOWN-LOSSY at high finding counts (a single
        # bounded generation condenses and drops items — observed ~0.91 coverage at 80
        # findings). The deduped findings union is the AUTHORITATIVE complete deliverable:
        # append it (announced) so coverage is never silently dropped. Never truncate
        # findings to fit the prose — that would delete real results.
        if len(findings) > _LOSSY_SYNTH_AT:
            appendix = "\n".join(f"- {f.claim} ({f.locator})" for f in findings)
            res.answer = (res.answer or "").rstrip() + (
                f"\n\n## Complete itemized findings ({len(findings)}, authoritative — the prose "
                f"above is a readable summary and is lossy at this scale)\n{appendix}")
            res.caps_announced.append(
                f"prose synthesis is lossy at scale ({len(findings)} findings); appended the complete "
                f"deduped union as the authoritative list (no findings dropped)")
    return res


# ---------------------------------------------------------------------------
# EXHAUSTIVE ENUMERATION — the map-reduce-union coverage primitive.
#
# research_corpus is tuned for "surface the NOTABLE things": each worker emits a
# capped JSON findings list, reconciled by salience. That structurally under-recovers
# a TOTAL-COVERAGE ask ("list EVERY entity / endpoint / call-site / symbol"), where the
# answer is a flat exhaustive set and the only job is to miss nothing. This primitive is
# the right shape for that: chunk -> fan out one raw ENUMERATOR per chunk (plain one-per-
# line text, no JSON bottleneck, generous token budget) -> union + dedupe. retry_empty
# refills any chunk a flaky/token-starved worker dropped, so a hole can't silently cap
# recall. And it routes a corpus that fits ONE pass to a single read (no lossy fan-out
# when there's no coverage benefit — discernment at the corpus level).
# ---------------------------------------------------------------------------

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
# a "LABEL: value" prefix the worker sometimes adds (PERSON:, LOCATION:, ORG:, Entity:) — keep the value
_LABEL = re.compile(r"^(?:[A-Z][A-Za-z]{1,14}|[A-Z]{2,6})\s*:\s*(?=\S)")
# conversational scaffolding that is not an item (bare category headers are caught by the trailing-colon
# rule instead, so this stays focused on non-colon framing and doesn't eat a real "PERSON: value")
_FRAMING = re.compile(
    r"^(here (are|is)|the following|these are|list of|that('| i)s all|in summary|"
    r"no (other|further|more)\b|i (found|could|will)|sure[,!]|okay\b)",
    re.IGNORECASE)


@dataclass
class EnumerationResult:
    instruction: str = ""
    items: List[str] = field(default_factory=list)   # deduped, in first-seen order
    n_chunks: int = 0
    chunks_covered: int = 0                            # chunks that returned usable output
    single_pass: bool = False                          # corpus fit one read -> no fan-out
    caps_announced: List[str] = field(default_factory=list)


def _enumeration_prompt(instruction: str, text: str) -> str:
    return (
        f"List EVERY {instruction} mentioned anywhere in the text below. Output ONLY a plain list, "
        "one item per line — no numbering, no commentary, no grouping, no markdown. Be exhaustive: "
        "include every distinct item, do not stop early, do not summarize.\n\n"
        f"=== TEXT ===\n{text}"
    )


def _split_inline_list(s: str) -> List[str]:
    """A worker sometimes lists items comma/semicolon-separated on ONE line, which would otherwise
    collapse to a single 'item' and crater recall. Split only when it clearly IS a list — 3+ pieces,
    each a short 1-3 word name — so a single entity that legitimately contains a comma ('Smith, John',
    'New York, NY') is left intact (2 pieces, or long pieces -> no split)."""
    if ";" in s:
        parts = [p.strip() for p in s.split(";")]
    elif s.count(",") >= 2:
        parts = [p.strip() for p in s.split(",")]
    else:
        return [s]
    parts = [p for p in parts if p]
    if len(parts) >= 3 and all(0 < len(p) <= 40 and len(p.split()) <= 3 for p in parts):
        return parts
    return [s]


def _parse_items(text: str) -> List[str]:
    out = []
    for line in (text or "").splitlines():
        s = _BULLET.sub("", line).strip().strip("*#`").strip().strip("\"'").strip()
        if not s or len(s) > 200:
            continue
        s = _LABEL.sub("", s).strip()  # strip a "PERSON:"/"ORG:" prefix FIRST, keep the value
        if s.lower() in ("none", "n/a", "na", "(none)") or s.endswith(":"):
            continue  # blanks, 'none', and bare header lines ("Entities:")
        if _FRAMING.match(s):
            continue  # conversational scaffolding ("Here are the entities", "That's all")
        for item in _split_inline_list(s):
            item = item.strip().strip("*#`").strip()
            if item and item.lower() not in ("none", "n/a", "na"):
                out.append(item)
    return out


def enumerate_corpus(
    sections: List[str],
    instruction: str,
    *,
    delegate_fn: Optional[Callable[..., str]] = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    config: Optional[UltracodeConfig] = None,
    agent: Any = None,
    concurrency: int = 16,
    retry_empty: int = 2,
    normalize: Optional[Callable[[str], str]] = None,
    single_pass_chars: int = 12000,
    progress: Optional[Callable[[str], None]] = None,
) -> EnumerationResult:
    """Exhaustively enumerate ``instruction`` items across pre-chunked ``sections``.

    Each section becomes one raw enumerator subagent; their line-lists are unioned and
    deduped (case/whitespace-insensitive by default, or via ``normalize``). ``retry_empty``
    refills dropped chunks. If the whole corpus fits ``single_pass_chars`` it does ONE read
    instead of fanning out (avoids the fan-out's overhead/fragmentation when one pass suffices).
    """
    cfg = config or UltracodeConfig()
    norm = normalize or (lambda s: " ".join(s.lower().split()))
    res = EnumerationResult(instruction=instruction, n_chunks=len(sections))
    sections = [s for s in sections if s and s.strip()]
    if not sections:
        res.caps_announced.append("no non-empty sections supplied")
        return res

    def _collect(raw_outputs: List[str]) -> None:
        seen, covered = {}, 0
        for out in raw_outputs:
            if out and out.strip():
                covered += 1
            for item in _parse_items(out):
                key = norm(item)
                if key and key not in seen:
                    seen[key] = item
        res.items = list(seen.values())
        res.chunks_covered = covered

    total_chars = sum(len(s) for s in sections)
    if total_chars <= single_pass_chars and aux_call_fn is not None:
        # fits one pass: a single read is more faithful than chunk->union (no fragmentation)
        res.single_pass = True
        res.n_chunks = 1
        if progress:
            progress(f"enumeration: corpus fits one pass ({total_chars} chars) -> single read")
        from ultracode.adapters import aux_call
        text = aux_call([{"role": "system", "content": "You are an exhaustive extractor. List every item, "
                          "one per line, never summarize."},
                         {"role": "user", "content": _enumeration_prompt(instruction, "\n\n".join(sections))}],
                        max_tokens=8000, call_fn=aux_call_fn)
        _collect([text])
        res.caps_announced.append(
            f"single-pass enumeration ({total_chars} chars fit one read): {len(res.items)} unique items")
        return res

    if progress:
        progress(f"enumeration: {len(sections)} sections, concurrency {concurrency}, retry_empty {retry_empty}")
    tasks = [{"goal": _enumeration_prompt(instruction, s)} for s in sections]
    results = delegate_fanout(tasks, parent_agent=agent, max_children=cfg.max_children,
                              concurrency=concurrency, delegate_fn=delegate_fn, retry_empty=retry_empty)
    _collect([str(e.get("summary") or "") for e in results if isinstance(e, dict)])
    dropped = len(sections) - res.chunks_covered
    res.caps_announced.append(
        f"enumerated {len(res.items)} unique items from {res.chunks_covered}/{len(sections)} sections")
    if dropped:
        res.caps_announced.append(
            f"WARNING: {dropped} section(s) returned no output even after {retry_empty} refill rounds — "
            f"coverage may be incomplete (raise retry_empty or lower per-chunk size)")
    return res
