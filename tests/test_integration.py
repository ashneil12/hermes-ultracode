"""Tests for the host-integration surface: threadsafe_delegate, ultracode_run wiring, and the
one-command installer. No network — all bridges are fakes."""

import threading

import pytest

from ultracode import integration, install


# ---- threadsafe_delegate ----------------------------------------------------

def test_threadsafe_delegate_passes_through_and_returns():
    seen = {}

    def fake(*, tasks, parent_agent=None, role="leaf"):
        seen["tasks"], seen["role"], seen["agent"] = tasks, role, parent_agent
        return "[ok]"

    d = integration.threadsafe_delegate(fake)
    out = d(tasks=[{"task": "x"}], parent_agent="A", role="worker")
    assert out == "[ok]"
    assert seen == {"tasks": [{"task": "x"}], "role": "worker", "agent": "A"}


def test_threadsafe_delegate_serializes_concurrent_calls():
    # the host fn is non-reentrant-hostile: assert it's never entered concurrently
    inside = {"n": 0, "max": 0}
    barrier = threading.Lock()

    def fake(*, tasks, parent_agent=None, role="leaf"):
        with barrier:
            inside["n"] += 1
            inside["max"] = max(inside["max"], inside["n"])
        # spin a little so overlap would be observable if the lock were absent
        for _ in range(10000):
            pass
        with barrier:
            inside["n"] -= 1
        return "ok"

    d = integration.threadsafe_delegate(fake)
    threads = [threading.Thread(target=lambda: d(tasks=[], role="leaf")) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert inside["max"] == 1  # never two host calls in flight at once


def test_ultracode_run_wires_threadsafe_delegate(monkeypatch):
    captured = {}

    def fake_run(task, *, context, agent, delegate_fn, aux_call_fn, config, **kw):
        captured.update(task=task, context=context, agent=agent,
                        delegate_fn=delegate_fn, config=config, kw=kw)
        return "RESULT"

    monkeypatch.setattr(integration, "run", fake_run)
    out = integration.ultracode_run(
        "do the thing", parent_agent="AGENT", context="src",
        concurrency=4, execution_assist=True, extra_flag=123)

    assert out == "RESULT"
    assert captured["task"] == "do the thing"
    assert captured["agent"] == "AGENT"
    assert captured["context"] == "src"
    assert captured["config"].concurrency == 4
    assert captured["config"].execution_assist is True
    assert captured["kw"] == {"extra_flag": 123}
    # the delegate handed to run is the thread-safe wrapper, not a raw fn
    assert callable(captured["delegate_fn"])


# ---- installer --------------------------------------------------------------

def _fake_agent(tmp_path, *, locked=True):
    (tmp_path / "tools").mkdir()
    (tmp_path / "agent").mkdir()
    lock = "import threading\n_lock = threading.Lock()\n" if locked else "# no lock here\n"
    (tmp_path / "tools" / "delegate_tool.py").write_text(lock + "def delegate_task(**k): ...\n")
    (tmp_path / "agent" / "auxiliary_client.py").write_text("def call_llm(**k): ...\n")
    return tmp_path


def test_install_check_is_dry_run(tmp_path, capsys):
    host = _fake_agent(tmp_path)
    rc = install.install(host, check=True, write_example=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "would vendor" in out
    assert not (host / "ultracode").exists()           # nothing copied
    assert not (host / "ultracode_quickstart.py").exists()


def test_install_vendors_package_and_quickstart(tmp_path, capsys):
    host = _fake_agent(tmp_path)
    rc = install.install(host, check=False, write_example=True)
    assert rc == 0
    # the self-contained package landed, importable modules present, heavy dirs skipped
    pkg = host / "ultracode"
    assert (pkg / "harness.py").is_file()
    assert (pkg / "integration.py").is_file()
    assert not (pkg / "__pycache__").exists()
    assert (host / "ultracode_quickstart.py").is_file()
    assert "from ultracode.integration import ultracode_run" in capsys.readouterr().out


def test_install_reports_missing_bridges(tmp_path, capsys):
    # an agent with neither bridge: install still succeeds (DI fallback) but warns
    rc = install.install(tmp_path, check=True, write_example=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "MISSING" in out


def test_install_flags_unlocked_delegate(tmp_path, capsys):
    host = _fake_agent(tmp_path, locked=False)
    install.install(host, check=True, write_example=False)
    out = capsys.readouterr().out
    assert "no lock" in out or "threadsafe_delegate serializes it" in out


def test_install_rejects_nonexistent_path(tmp_path):
    assert install.install(tmp_path / "nope", check=True, write_example=False) == 2
