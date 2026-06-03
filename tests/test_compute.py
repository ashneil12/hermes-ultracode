"""Tests for execution-as-reasoning-aid (no live model; real subprocess for run_python)."""

from ultracode.compute import computable_answer
from ultracode.config import UltracodeConfig
from ultracode.harness import run


def test_computable_answer_runs_a_program():
    # the agent 'writes' a program; run_python actually executes it.
    def aux(**kwargs):
        return "Here is the program:\n```python\nprint(sum(range(1, 11)))\n```"
    r = computable_answer("Sum 1..10.", aux_call_fn=aux)
    assert r.ran and r.answer == "55" and not r.declined


def test_computable_answer_declines_pure_reasoning():
    def aux(**kwargs):
        return "NOT_COMPUTABLE"
    r = computable_answer("A says B is a knave...", aux_call_fn=aux)
    assert r.declined and not r.ran


def test_computable_answer_retries_on_error():
    calls = {"n": 0}
    def aux(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "```python\nprint(undefined_name)\n```"   # NameError
        return "```python\nprint(6 * 7)\n```"                 # fixed
    r = computable_answer("compute 6*7", aux_call_fn=aux)
    assert r.ran and r.answer == "42" and calls["n"] == 2     # retried once with the error


def test_harness_execution_assist_folds_compute_as_evidence():
    # AUGMENT not replace: the computed value is folded into the material as evidence and the
    # reasoning path produces the final answer (so multi-part/completeness is never lost).
    def aux(**kwargs):
        sysm = kwargs["messages"][0]["content"].lower()
        if "writing and running code" in sysm:   # the compute system prompt
            return "```python\nprint(100001101010)\n```"
        return kwargs["messages"][-1]["content"]  # solo path: echo so we can see the injected evidence
    res = run("Find the smallest multiple of 2026 using only digits 0 and 1.",
              aux_call_fn=aux, delegate_fn=lambda **k: "{}", enable_ledger=False,
              config=UltracodeConfig(execution_assist=True))
    assert res.mode != "compute"                                   # does NOT short-circuit
    assert "100001101010" in res.answer                            # computed value reached the answer via reasoning
    assert any("execution evidence" in c for c in res.caps_announced)


def test_execution_assist_off_by_default_unchanged():
    # with the flag off, no compute attempt; normal solo path
    def aux(**kwargs):
        return "solo answer"
    res = run("hi there", aux_call_fn=aux, delegate_fn=lambda **k: "{}", enable_ledger=False)
    assert res.mode == "solo"
