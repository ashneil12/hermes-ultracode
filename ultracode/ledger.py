"""Durable, append-only JSONL run ledger.

Every ultracode run writes a line-per-event record under
``$HERMES_HOME/ultracode-runs/<run_id>.jsonl`` so a run is auditable and
resumable, and so the completeness critic and the user-facing report can be
reconstructed from disk rather than held only in memory.

Kept dependency-light on purpose (the kanban control-plane in CONTRACTS.md §6 is
the heavier alternative we can graduate to later). The clock is injectable so
tests are deterministic.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ultracode.schema import Finding, StageResult


def _default_root() -> Path:
    try:
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home()) / "ultracode-runs"
    except Exception:
        return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "ultracode-runs"


class RunLedger:
    """Append-only JSONL writer for one ultracode run.

        led = RunLedger("run-123")
        led.event("start", {"task": task})
        led.stage(stage_result)
        led.event("done", {"survived": 7})
        report = led.read()           # list of event dicts
    """

    def __init__(
        self,
        run_id: str,
        *,
        root: Optional[Path] = None,
        path: Optional[Path] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.run_id = run_id
        self._clock = clock
        self._seq = 0
        if path is not None:
            self.path = Path(path)
        else:
            base = Path(root) if root is not None else _default_root()
            base.mkdir(parents=True, exist_ok=True)
            self.path = base / f"{run_id}.jsonl"

    # ---- writing ----------------------------------------------------------
    def event(self, kind: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rec = {
            "seq": self._seq,
            "t": round(self._clock(), 3),
            "run_id": self.run_id,
            "kind": kind,
            "payload": payload or {},
        }
        self._seq += 1
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def stage(self, result: StageResult) -> Dict[str, Any]:
        """Record a whole pipeline stage (findings + announced caps)."""
        return self.event("stage", result.as_dict())

    def finding(self, f: Finding) -> Dict[str, Any]:
        return self.event("finding", f.as_dict())

    def cap(self, message: str) -> Dict[str, Any]:
        """Explicitly record an announced cap/truncation (no-silent-caps)."""
        return self.event("cap_announced", {"message": message})

    # ---- reading ----------------------------------------------------------
    def read(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return out

    def findings(self) -> List[Finding]:
        """Reconstruct every Finding recorded (from 'finding' and 'stage' events)."""
        out: List[Finding] = []
        for rec in self.read():
            if rec.get("kind") == "finding":
                out.append(Finding.from_dict(rec["payload"]))
            elif rec.get("kind") == "stage":
                for fd in rec.get("payload", {}).get("findings", []):
                    out.append(Finding.from_dict(fd))
        return out

    def caps(self) -> List[str]:
        caps: List[str] = []
        for rec in self.read():
            if rec.get("kind") == "cap_announced":
                caps.append(rec["payload"].get("message", ""))
            elif rec.get("kind") == "stage":
                caps.extend(rec.get("payload", {}).get("caps_announced", []))
        return [c for c in caps if c]
