"""Unit tests for ultracode.reasoning — effort floor + snapshot/restore."""

from ultracode.reasoning import build_reasoning_config, effort_scope


def test_build_reasoning_config_levels():
    assert build_reasoning_config("xhigh") == {"enabled": True, "effort": "xhigh"}
    assert build_reasoning_config("high") == {"enabled": True, "effort": "high"}
    assert build_reasoning_config("  XHIGH ") == {"enabled": True, "effort": "xhigh"}
    assert build_reasoning_config("none") == {"enabled": False}
    assert build_reasoning_config(None) == {"enabled": True, "effort": "xhigh"}


def test_build_reasoning_config_unknown_biases_up():
    cfg = build_reasoning_config("very-high")
    assert cfg["enabled"] is True
    assert cfg["effort"] == "xhigh"  # bias UP, not to medium
    assert cfg["_coerced_from"] == "very-high"


class _Agent:
    def __init__(self, rc):
        self.reasoning_config = rc


def test_effort_scope_sets_and_restores():
    a = _Agent({"enabled": True, "effort": "medium"})
    with effort_scope(a, "xhigh"):
        assert a.reasoning_config == {"enabled": True, "effort": "xhigh"}
    assert a.reasoning_config == {"enabled": True, "effort": "medium"}


def test_effort_scope_restores_on_exception():
    a = _Agent({"enabled": True, "effort": "low"})
    try:
        with effort_scope(a, "xhigh"):
            assert a.reasoning_config["effort"] == "xhigh"
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert a.reasoning_config == {"enabled": True, "effort": "low"}  # restored despite error


def test_effort_scope_none_agent_is_noop():
    with effort_scope(None, "xhigh"):
        pass  # must not raise


def test_effort_scope_agent_without_attr_restores_to_none():
    class Bare:
        pass

    b = Bare()
    with effort_scope(b, "xhigh"):
        assert b.reasoning_config == {"enabled": True, "effort": "xhigh"}
    assert b.reasoning_config is None
