"""Tests for deep research over a real on-disk corpus (no live model)."""

import json
import os

from ultracode.config import UltracodeConfig
from ultracode.corpus import relevance_rank, research_corpus
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
