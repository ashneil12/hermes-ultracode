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
    res.chunks_read = len(chunks)
    if progress:
        progress(f"extracting from {len(chunks)} chunks / {res.n_files} files (concurrency {concurrency})")

    tasks = [{"goal": _extract_prompt(question, c)} for c in chunks]
    results = delegate_fanout(tasks, parent_agent=agent, max_children=cfg.max_children,
                              concurrency=concurrency, delegate_fn=delegate_fn)
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
