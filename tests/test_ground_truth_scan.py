import importlib.util
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "ground_truth_scan.py"

spec = importlib.util.spec_from_file_location("ground_truth_scan", SCRIPT)
gts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gts)


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_ast_ignores_detector_strings_but_catches_real_shell_true(tmp_path):
    write(tmp_path / "scanner.py", '''
        RULES = ["subprocess.run(cmd, shell=True)", "eval(user)", "os.system(x)"]
    ''')
    write(tmp_path / "real.py", '''
        import subprocess
        def f(cmd):
            return subprocess.run(cmd, shell=True)
    ''')
    res = gts.scan(str(tmp_path))
    assert [s["file"] for s in res["sinks"]] == ["real.py"]
    assert res["sinks"][0]["sink"] == "subprocess+shell=True"


def test_yaml_safe_loader_variable_is_not_flagged(tmp_path):
    write(tmp_path / "safe_yaml.py", '''
        import yaml
        loader = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
        def load(value):
            return yaml.load(value, Loader=loader)
    ''')
    res = gts.scan(str(tmp_path))
    assert res["sinks"] == []


def test_ruamel_yaml_is_downgraded_not_unsafe(tmp_path):
    write(tmp_path / "rt_yaml.py", '''
        from ruamel.yaml import YAML
        yaml = YAML(typ="rt")
        def load(path):
            with open(path) as fh:
                return yaml.load(fh)
    ''')
    res = gts.scan(str(tmp_path))
    assert len(res["sinks"]) == 1
    assert res["sinks"][0]["sink"] == "yaml.load (ruamel/verify-loader)"


def test_catches_false_negative_sink_classes(tmp_path):
    write(tmp_path / "misses.py", '''
        import pickle, os, asyncio
        def a(b): return pickle.loads(b)
        def b(cmd): return os.system(cmd)
        async def c(cmd): return await asyncio.create_subprocess_shell(cmd)
        def d(name): return __import__(name)
    ''')
    res = gts.scan(str(tmp_path))
    kinds = {s["sink"] for s in res["sinks"]}
    assert "pickle (deserialize)" in kinds
    assert "os.shell-exec" in kinds
    assert "create_subprocess_shell" in kinds
    assert "__import__ (dynamic)" in kinds


def test_excludes_tests_by_path_segment(tmp_path):
    write(tmp_path / "tests" / "bad_test.py", '''
        import subprocess
        subprocess.run("x", shell=True)
    ''')
    write(tmp_path / "src" / "real.py", '''
        import subprocess
        subprocess.run("x", shell=True)
    ''')
    res = gts.scan(str(tmp_path))
    assert [s["file"] for s in res["sinks"]] == ["src/real.py"]
