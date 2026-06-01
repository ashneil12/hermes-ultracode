"""Unit tests for ultracode.ledger — durable JSONL run record."""

from ultracode.ledger import RunLedger
from ultracode.schema import Finding, StageResult, Verdict


def _clock():
    state = {"t": 1000.0}

    def tick():
        state["t"] += 1.0
        return state["t"]

    return tick


def test_event_roundtrip(tmp_path):
    led = RunLedger("run-1", path=tmp_path / "run-1.jsonl", clock=_clock())
    led.event("start", {"task": "find bugs"})
    led.event("done", {"survived": 3})
    recs = led.read()
    assert [r["kind"] for r in recs] == ["start", "done"]
    assert [r["seq"] for r in recs] == [0, 1]
    assert recs[0]["payload"]["task"] == "find bugs"
    assert recs[0]["t"] < recs[1]["t"]  # injected monotonic clock


def test_stage_and_finding_reconstruction(tmp_path):
    led = RunLedger("run-2", path=tmp_path / "run-2.jsonl")
    sr = StageResult(
        stage="find",
        findings=[Finding(claim="leak", locator="a.py:1", verdict=Verdict.CONFIRMED)],
        caps_announced=["finder pool capped at 6"],
    )
    led.stage(sr)
    led.finding(Finding(claim="extra", locator="b.py:2"))
    led.cap("discovery stopped after 2 dry rounds")

    findings = led.findings()
    assert {f.claim for f in findings} == {"leak", "extra"}
    leak = next(f for f in findings if f.claim == "leak")
    assert leak.verdict == Verdict.CONFIRMED

    caps = led.caps()
    assert "finder pool capped at 6" in caps
    assert "discovery stopped after 2 dry rounds" in caps


def test_read_missing_file_is_empty(tmp_path):
    led = RunLedger("ghost", path=tmp_path / "nope.jsonl")
    assert led.read() == []
    assert led.findings() == []
    assert led.caps() == []


def test_default_root_under_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    led = RunLedger("run-3")
    led.event("start")
    assert led.path.exists()
    assert "ultracode-runs" in str(led.path)
