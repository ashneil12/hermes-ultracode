"""Tests for execution-based ground-truth verification (REAL subprocess runs)."""

import pytest

from ultracode.execute import extract_code, run_python
from ultracode.groundtruth import confirm_by_execution, ground_truth_pass
from ultracode.schema import Finding


def test_run_python_exit_zero():
    r = run_python("import sys\nsys.exit(0)")
    assert r.ok and r.returncode == 0 and not r.timed_out


def test_run_python_raises_nonzero():
    r = run_python("raise ValueError('boom')")
    assert not r.ok and "ValueError" in r.stderr


# Use thread-method timeout for THIS test: the global --timeout-method=signal fires
# SIGALRM, which on some Pythons (3.9) lands during run_python's subprocess waitpid and
# hangs the reap. run_python's own subprocess timeout is the real assertion here.
@pytest.mark.timeout(method="thread")
def test_run_python_timeout():
    r = run_python("import time\ntime.sleep(30)", timeout=1.0)  # idle child: clean SIGKILL reap
    assert r.timed_out and not r.ok


def test_run_python_isolated_env_has_no_secrets():
    # -I isolated mode + minimal env: a planted secret must NOT be visible
    r = run_python("import os\nprint(os.environ.get('DEEPSEEK_API_KEY', 'ABSENT'))")
    assert "ABSENT" in r.stdout


def test_extract_code_fenced_and_bare():
    assert extract_code("```python\nx=1\n```") == "x=1"
    assert extract_code("y=2") == "y=2"


def test_confirm_by_execution_reproduces():
    f = Finding(claim="checksum off-by-one raises IndexError", locator="x:1", severity="high")
    # fake model writes a repro that exits 0 IFF the IndexError happens
    repro = ("def checksum(items):\n"
             "    t=0\n"
             "    for i in range(len(items)+1):\n"
             "        t+=items[i]\n"
             "    return t\n"
             "try:\n"
             "    checksum([1,2,3]); raise SystemExit(1)\n"
             "except IndexError:\n"
             "    raise SystemExit(0)\n")
    gt = confirm_by_execution(f, "<code>", aux_call_fn=lambda **k: repro)
    assert gt["reproduced"] is True
    assert gt["exec"]["returncode"] == 0


def test_confirm_by_execution_does_not_reproduce():
    f = Finding(claim="this function crashes", locator="x:1", severity="high")
    # repro that does NOT reproduce -> exits 1
    gt = confirm_by_execution(f, "<code>", aux_call_fn=lambda **k: "import sys\nsys.exit(1)")
    assert gt["reproduced"] is False  # annotation only, never a kill


def test_arbiter_resurrects_killed_finding_that_reproduces():
    from ultracode.groundtruth import arbitrate_findings
    from ultracode.schema import Verdict
    # a REAL bug the skeptics wrongly killed; its repro reproduces -> resurrect
    f = Finding(claim="crash on empty input", locator="x:1", severity="high")
    f.survived = False
    f.verdict = Verdict.REFUTED
    arb = arbitrate_findings([f], "<code>", aux_call_fn=lambda **k: "import sys\nsys.exit(0)")
    assert arb["resurrected"] == 1
    assert f.survived is True and f.verdict == Verdict.CONFIRMED
    assert "RESURRECTED" in f.raw["arbiter"]


def test_arbiter_does_not_kill_on_nonrepro():
    from ultracode.groundtruth import arbitrate_findings
    f = Finding(claim="maybe a bug", locator="y:1", severity="high")
    f.survived = True
    arbitrate_findings([f], "<code>", aux_call_fn=lambda **k: "import sys\nsys.exit(1)")
    assert f.survived is True  # non-reproduction only annotates, never kills


def test_ground_truth_pass_annotates_and_counts():
    findings = [
        Finding(claim="real crash", locator="a:1", severity="critical"),
        Finding(claim="low nit", locator="b:2", severity="info"),  # skipped (severity filter)
    ]
    gt = ground_truth_pass(findings, "<code>", aux_call_fn=lambda **k: "import sys\nsys.exit(0)")
    assert gt == 1  # only the critical one was checked + reproduced
    assert findings[0].raw["ground_truth"]["reproduced"] is True
    assert "ground_truth" not in findings[1].raw  # info severity skipped
