"""Tests for deep research over a real on-disk corpus (no live model)."""

import json
import os

from ultracode.config import UltracodeConfig
from ultracode.corpus import enumerate_corpus, relevance_rank, research_corpus
from ultracode.repo import Chunk


def _write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text)


def test_research_corpus_reads_chunks_extracts_and_synthesizes(tmp_path):
    root = str(tmp_path)
    # two docs, each with a distinct fact only present in that file
    _write(root, "alpha.md", "Project Zephyr uses a 384-bit nonce.\n" + "filler\n" * 30)
    _write(root, "beta.md", "Project Quasar has a 12-node quorum.\n" + "filler\n" * 30)

    def fake_delegate(*, tasks, parent_agent, role):
        results = []
        for i, t in enumerate(tasks):
            goal = t["goal"]
            # each extractor reports only the fact in ITS section
            if "Zephyr" in goal:
                body = {"findings": [{"claim": "Project Zephyr uses a 384-bit nonce", "locator": "docs/alpha.md:1",
                                      "evidence": "stated", "severity": "info"}]}
            elif "Quasar" in goal:
                body = {"findings": [{"claim": "Project Quasar has a 12-node quorum", "locator": "docs/beta.md:1",
                                      "evidence": "stated", "severity": "info"}]}
            else:
                body = {"findings": []}
            results.append({"task_index": i, "status": "completed", "summary": json.dumps(body)})
        return json.dumps({"results": results})

    def fake_aux(**kwargs):
        # the landscape synthesizer: union both facts
        return "Zephyr: 384-bit nonce. Quasar: 12-node quorum."

    res = research_corpus(root, "List every project and its key configured value.",
                          ext=".md", delegate_fn=fake_delegate, aux_call_fn=fake_aux,
                          config=UltracodeConfig(), concurrency=4, min_file_lines=2)
    assert res.n_files == 2 and res.chunks_read >= 2
    claims = " ".join(f.claim for f in res.findings)
    assert "Zephyr" in claims and "Quasar" in claims           # both files were READ
    assert "384" in res.answer and "12-node" in res.answer      # union survived to the answer


def test_relevance_rank_orders_by_question_overlap():
    chunks = [
        Chunk(path="a", start=1, text="completely unrelated lorem ipsum content here"),
        Chunk(path="b", start=1, text="the quorum and consensus protocol details and raft leader election"),
    ]
    ranked = relevance_rank(chunks, "how does the consensus quorum and raft election work")
    assert ranked[0].path == "b"   # the relevant chunk ranks first


def test_research_corpus_appends_complete_union_at_scale(tmp_path):
    # prose synth is lossy at high finding counts -> the complete deduped union must be
    # appended (announced), so coverage is never silently dropped.
    root = str(tmp_path)
    for i in range(50):
        _write(root, f"f{i}.md", f"Fact: widget_{i} has property prop_{i}.\n" + "pad\n" * 12)

    def fake_delegate(*, tasks, parent_agent, role):
        results = []
        for i, t in enumerate(tasks):
            m = next((j for j in range(50) if f"widget_{j} " in t["goal"] or f"widget_{j}." in t["goal"]), None)
            # distinct locators (no shared token) so reconcile keeps them as 50 findings
            body = {"findings": [{"claim": f"widget_{m} has prop_{m}", "locator": f"componentZeta{m}",
                                  "evidence": "x", "severity": "info"}]} if m is not None else {"findings": []}
            results.append({"task_index": i, "status": "completed", "summary": json.dumps(body)})
        return json.dumps({"results": results})

    # the synthesizer deliberately drops most items (simulating lossy condensation)
    def lossy_aux(**kwargs):
        return "Summary: there are several widgets including widget_0 and widget_1."

    res = research_corpus(root, "List every widget and its property.", ext=".md",
                          delegate_fn=fake_delegate, aux_call_fn=lossy_aux,
                          config=UltracodeConfig(), min_file_lines=2)
    assert len(res.findings) >= 45                       # extraction recovered ~all
    # the lossy prose alone would miss most; the appended union must contain every widget
    assert "widget_49" in res.answer and "widget_30" in res.answer
    assert any("authoritative" in c.lower() for c in res.caps_announced)  # announced, not silent


def test_research_corpus_topk_retrieval_announces_skips(tmp_path):
    root = str(tmp_path)
    for i in range(6):
        _write(root, f"d{i}.md", f"section {i} about topic {i}\n" + "x\n" * 20)

    def fake_delegate(*, tasks, parent_agent, role):
        return json.dumps({"results": [{"task_index": i, "status": "completed",
                                        "summary": json.dumps({"findings": []})} for i in range(len(tasks))]})

    res = research_corpus(root, "topic 2", ext=".md", delegate_fn=fake_delegate, aux_call_fn=None,
                          config=UltracodeConfig(), top_k_chunks=2, synthesize=False, min_file_lines=2)
    assert res.chunks_read == 2                                   # only top-K read
    assert any("skipped" in c.lower() and "announced" in c.lower() for c in res.caps_announced)  # not silent


# ---- enumerate_corpus: the map-reduce-union coverage primitive ----

def _enum_delegate(per_section_items):
    """A fake delegate that returns the given plain-text item-list for each section, by index."""
    def fake(*, tasks, parent_agent, role):
        results = []
        for i, _t in enumerate(tasks):
            items = per_section_items[i % len(per_section_items)]
            results.append({"task_index": i, "status": "completed", "summary": "\n".join(items)})
        return json.dumps({"results": results})
    return fake


def test_enumerate_corpus_unions_and_dedupes_across_sections():
    sections = ["sec A text", "sec B text", "sec C text"]
    # overlapping lists across sections; expect the deduped union, first-seen order
    delegate = _enum_delegate([["London", "Acme Corp"], ["acme corp", "Berlin"], ["London", "Carol"]])
    res = enumerate_corpus(sections, "named entity", delegate_fn=delegate,
                           config=UltracodeConfig(max_children=3), concurrency=3)
    assert res.items == ["London", "Acme Corp", "Berlin", "Carol"]   # case-insensitive dedupe, order kept
    assert res.chunks_covered == 3
    assert not res.single_pass


def test_enumerate_corpus_strips_bullets_and_noise():
    delegate = _enum_delegate([["- London", "1. Berlin", "none", "  * Acme  "]])
    res = enumerate_corpus(["x"], "entity", delegate_fn=delegate, config=UltracodeConfig())
    assert res.items == ["London", "Berlin", "Acme"]   # bullets/numbering stripped, 'none' dropped


def test_parse_items_robust_to_messy_worker_output():
    # the failure modes real reasoning-model workers exhibit — found by probing, now regression-locked
    from ultracode.corpus import _parse_items
    # preamble + bullets + numbering + closing scaffolding
    assert _parse_items("Here are the entities:\n- London\n* U.S.\n1. Berlin\nThat is all.") == \
        ["London", "U.S.", "Berlin"]
    # "LABEL: value" prefixes stripped, value kept (NOT dropped as a category header)
    assert _parse_items("PERSON: John Smith\nLOCATION: Paris\nORG: NATO") == ["John Smith", "Paris", "NATO"]
    # an inline comma/semicolon list must split (else it collapses to one item and craters recall)
    assert _parse_items("London, Berlin, Paris") == ["London", "Berlin", "Paris"]
    assert _parse_items("Apple; Google; Microsoft") == ["Apple", "Google", "Microsoft"]
    # but a single entity that legitimately contains a comma must NOT split
    assert _parse_items("Smith, John\nNew York City") == ["Smith, John", "New York City"]
    # bare category header dropped, markdown stripped
    assert _parse_items("**Entities:**\nLondon") == ["London"]


def test_enumerate_corpus_splits_inline_lists_in_union():
    # a worker that returns a comma-joined line still contributes every entity to the union
    delegate = _enum_delegate([["London, Berlin, Paris"], ["Acme, Globex, Initech"]])
    res = enumerate_corpus(["s1", "s2"], "entity", delegate_fn=delegate,
                           config=UltracodeConfig(max_children=2), concurrency=2)
    assert set(res.items) == {"London", "Berlin", "Paris", "Acme", "Globex", "Initech"}


def test_enumerate_corpus_retries_empty_sections():
    seen = {}

    def flaky(*, tasks, parent_agent, role):
        # the section carrying the marker "QQZ" returns empty the first time, fills on retry
        results = []
        for i, t in enumerate(tasks):
            has_marker = "QQZ" in t["goal"]
            key = "marked" if has_marker else "plain"
            n = seen.get(key, 0); seen[key] = n + 1
            empty = (has_marker and n == 0)
            results.append({"task_index": i, "status": "completed" if not empty else "error",
                            "summary": "" if empty else ("Item-Marked" if has_marker else "Item-Plain")})
        return json.dumps({"results": results})

    res = enumerate_corpus(["plain section", "section QQZ here"], "thing", delegate_fn=flaky,
                           config=UltracodeConfig(max_children=2), concurrency=2, retry_empty=2)
    assert set(res.items) == {"Item-Plain", "Item-Marked"}   # the empty section was refilled
    assert res.chunks_covered == 2
    assert seen["plain"] == 1 and seen["marked"] == 2         # only the empty section retried


def test_enumerate_corpus_single_pass_when_corpus_fits():
    # small corpus + an aux_call_fn -> ONE read, no fan-out
    def fake_aux(**kwargs):
        return "London\nBerlin\nAcme Corp"

    called = {"delegate": 0}

    def should_not_run(**kwargs):
        called["delegate"] += 1
        return "{}"

    res = enumerate_corpus(["tiny corpus"], "entity", delegate_fn=should_not_run,
                           aux_call_fn=fake_aux, single_pass_chars=10000)
    assert res.single_pass is True
    assert res.items == ["London", "Berlin", "Acme Corp"]
    assert called["delegate"] == 0                    # fan-out skipped entirely
