"""Unit tests for ultracode.mode — the /ultracode toggle (snapshot/restore)."""

from ultracode import mode


class _Agent:
    def __init__(self):
        self.reasoning_config = {"enabled": True, "effort": "medium"}
        self.ephemeral_system_prompt = None


def test_enable_sets_xhigh_and_directive():
    a = _Agent()
    msg = mode.enable(a)
    assert "ON" in msg
    assert a.reasoning_config == {"enabled": True, "effort": "xhigh"}
    assert "ULTRACODE MODE" in a.ephemeral_system_prompt
    assert mode.is_enabled(a)


def test_disable_restores_prior_state():
    a = _Agent()
    mode.enable(a)
    mode.disable(a)
    assert a.reasoning_config == {"enabled": True, "effort": "medium"}
    assert a.ephemeral_system_prompt is None
    assert not mode.is_enabled(a)


def test_enable_is_idempotent():
    a = _Agent()
    mode.enable(a)
    first = a.ephemeral_system_prompt
    assert mode.enable(a) == "ultracode: already on"
    assert a.ephemeral_system_prompt == first  # not double-appended


def test_enable_preserves_prior_ephemeral():
    a = _Agent()
    a.ephemeral_system_prompt = "PRIOR CONTEXT"
    mode.enable(a)
    assert a.ephemeral_system_prompt.startswith("PRIOR CONTEXT")
    assert "ULTRACODE MODE" in a.ephemeral_system_prompt
    mode.disable(a)
    assert a.ephemeral_system_prompt == "PRIOR CONTEXT"


def test_handle_command_dispatch():
    a = _Agent()
    assert "ON" in mode.handle_command(a, "on")
    assert "ON" in mode.handle_command(a, "status").upper() or "on" in mode.handle_command(a, "status")
    assert "OFF" in mode.handle_command(a, "off")
    # bare toggle flips
    assert "ON" in mode.handle_command(a, "")
    assert "OFF" in mode.handle_command(a, "")


def test_none_agent_is_safe():
    assert "no agent" in mode.enable(None)
    assert "no agent" in mode.disable(None)
    assert not mode.is_enabled(None)
