"""Tests for task generalization: kind classification + judge-panel."""

import json

from ultracode.config import UltracodeConfig
from ultracode.harness import run
from ultracode.judge import judge_panel
from ultracode.kinds import TaskKind, classify_kind, skeptic_instruction, worker_instruction


def test_classify_kind():
    assert classify_kind("find all security bugs in this code") == TaskKind.CODE
    assert classify_kind("audit this function for vulnerabilities") == TaskKind.CODE
    assert classify_kind("write a catchy tagline for our product") == TaskKind.GENERATIVE
    assert classify_kind("research the current state of fusion energy") == TaskKind.RESEARCH
    assert classify_kind("analyze the tradeoffs between Postgres and MySQL") == TaskKind.ANALYSIS
    assert classify_kind("why does my deploy keep failing") in (TaskKind.QA, TaskKind.CODE)


def test_kind_specific_instructions_differ():
    assert "source" in worker_instruction(TaskKind.RESEARCH).lower()
    assert "bug" in worker_instruction(TaskKind.CODE).lower()
    assert "citogenesis" in skeptic_instruction(TaskKind.RESEARCH).lower()


def _judge_fakes(winner_angle="rigorous"):
    def delegate(*, tasks, parent_agent, role):
        results = []
        for i, t in enumerate(tasks):
            g = t["goal"]
            if "Score this candidate" in g:
                results.append({"task_index": i, "status": "completed",
                                "summary": json.dumps({"score": 9 if winner_angle in g else 5, "strengths": ["s"]})})
            else:  # candidate generation
                results.append({"task_index": i, "status": "completed", "summary": f"candidate {i}: a draft"})
        return json.dumps({"results": results})

    def aux(**kwargs):
        return "FINAL: the synthesized winning artifact"

    return aux, delegate


def test_judge_panel_generates_scores_synthesizes():
    aux, delegate = _judge_fakes()
    jr = judge_panel("write a tagline for an AI agent", delegate_fn=delegate, aux_call_fn=aux,
                     config=UltracodeConfig(max_finders=4))
    assert jr.answer == "FINAL: the synthesized winning artifact"
    assert len(jr.candidates) >= 2
    assert jr.scores  # judges ran
    assert "rigorous" in jr.winner_angle  # highest-scored angle won


def test_harness_routes_generative_to_judge_panel():
    aux, delegate = _judge_fakes()
    res = run("write a punchy tagline", kind="generative", force_orchestrate=True,
              aux_call_fn=aux, delegate_fn=delegate, enable_ledger=False)
    assert res.mode == "judge-panel"
    assert "synthesized" in res.answer
    assert any("candidates" in c for c in res.caps_announced)
