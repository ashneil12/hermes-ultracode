"""Unit tests for ultracode.adapters — JSON extraction + DI fan-out, no runtime."""

import json

from ultracode.adapters import (
    aux_call,
    delegate_fanout,
    extract_json,
    runtime_from_agent,
)


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    text = "Here is the plan:\n```json\n{\"mode\": \"parallel\"}\n```\nthanks"
    assert extract_json(text) == {"mode": "parallel"}


def test_extract_json_embedded_prose():
    text = 'Sure! The result is {"subtasks": [{"goal": "x"}]} as requested.'
    assert extract_json(text) == {"subtasks": [{"goal": "x"}]}


def test_extract_json_trailing_comma_repair():
    assert extract_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_extract_json_failure_returns_none():
    assert extract_json("no json here at all") is None
    assert extract_json("") is None
    assert extract_json(None) is None


def test_delegate_fanout_single_wave():
    calls = {}

    def fake_delegate(*, tasks, parent_agent, role):
        calls["tasks"] = tasks
        calls["role"] = role
        results = [
            {"task_index": i, "status": "completed", "summary": f"did {t['goal']}"}
            for i, t in enumerate(tasks)
        ]
        return json.dumps({"results": results, "total_duration_seconds": 1.0})

    tasks = [{"goal": "a"}, {"goal": "b"}]
    out = delegate_fanout(tasks, parent_agent=object(), role="leaf", max_children=3, delegate_fn=fake_delegate)
    assert len(out) == 2
    assert out[0]["summary"] == "did a"
    assert calls["role"] == "leaf"


def test_delegate_fanout_chunks_into_waves_and_globalizes_index():
    seen_waves = []

    def fake_delegate(*, tasks, parent_agent, role):
        seen_waves.append(len(tasks))
        results = [{"task_index": i, "status": "completed", "summary": t["goal"]} for i, t in enumerate(tasks)]
        return json.dumps({"results": results})

    tasks = [{"goal": str(i)} for i in range(5)]
    out = delegate_fanout(tasks, parent_agent=None, max_children=2, delegate_fn=fake_delegate)
    assert seen_waves == [2, 2, 1]  # chunked by cap
    assert [e["task_index"] for e in out] == [0, 1, 2, 3, 4]  # global, not wave-local
    assert [e["summary"] for e in out] == ["0", "1", "2", "3", "4"]


def test_delegate_fanout_handles_error_envelope():
    def fake_delegate(*, tasks, parent_agent, role):
        return json.dumps({"error": "too many tasks"})

    out = delegate_fanout([{"goal": "x"}], delegate_fn=fake_delegate)
    assert out[0]["status"] == "error"
    assert "too many" in out[0]["error"]


def test_delegate_fanout_empty():
    assert delegate_fanout([], delegate_fn=lambda **k: "{}") == []


def test_aux_call_with_openai_shaped_fake():
    class _Msg:
        content = "hello"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    captured = {}

    def fake_call(**kwargs):
        captured.update(kwargs)
        return _Resp()

    out = aux_call([{"role": "user", "content": "hi"}], temperature=0.2, call_fn=fake_call)
    assert out == "hello"
    assert captured["tools"] is None  # tools-off invariant
    assert captured["temperature"] == 0.2


def test_aux_call_with_dict_fake():
    def fake_call(**kwargs):
        return {"choices": [{"message": {"content": "world"}}]}

    assert aux_call([], call_fn=fake_call) == "world"


def test_aux_call_with_string_fake():
    assert aux_call([], call_fn=lambda **k: "plain") == "plain"


def test_runtime_from_agent():
    class A:
        model = "kr/claude-opus-4.8"
        provider = "nous"
        base_url = "https://x"
        api_key = "secret"
        api_mode = "anthropic_messages"

    rt = runtime_from_agent(A())
    assert rt["model"] == "kr/claude-opus-4.8"
    assert runtime_from_agent(None) is None
