"""HumanEval (code generation, pass@1) — single-shot vs ultracode self-repair loop.

Recognized coding benchmark. The ultracode pattern here is execution-feedback self-repair:
generate the function, RUN the provided tests, and if they fail, feed the failure back and
refine (up to K rounds). This is exactly where a weak coder benefits — the runtime is the
ground truth, so flash iterates to a passing solution instead of one-shotting a bug.

  python bench/humaneval_bench.py single     deepseek-v4-flash 164
  python bench/humaneval_bench.py ultracode  deepseek-v4-flash 164
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultracode.compute import _fenced_code
from ultracode.execute import run_python
from bench.deepseek_client import DeepSeekClient

DATA = Path(__file__).resolve().parent / "data" / "HumanEval.jsonl"
RES = Path(__file__).resolve().parent / "results"
MAX_REPAIR = 3


def load(n):
    return [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()][:n]


def _program(code, p):
    # the model returns a complete function; run it against the official tests
    return f"{code}\n\n{p['test']}\n\ncheck({p['entry_point']})\n"


def _passes(code, p):
    if not code:
        return False
    r = run_python(_program(code, p), timeout=10.0)
    return r.ok


def _gen(client, prompt, extra=""):
    msg = [{"role": "system", "content": "You are an expert Python programmer. Complete the function. "
            "Return the COMPLETE function (signature + body) in one ```python code block, nothing else."},
           {"role": "user", "content": prompt + extra}]
    return _fenced_code(type(client)._content(client.chat(msg, temperature=0.2, max_tokens=1500)))


def solve_single(model, p):
    c = DeepSeekClient(model=model, max_workers=2)
    return _passes(_gen(c, p["prompt"]), p)


def solve_ultracode(model, p):
    # generate -> run tests -> on failure, refine with the actual error (execution-feedback loop)
    c = DeepSeekClient(model=model, max_workers=2)
    code = _gen(c, p["prompt"])
    for _ in range(MAX_REPAIR):
        prog = _program(code, p) if code else ""
        r = run_python(prog, timeout=10.0) if code else None
        if r and r.ok:
            return True
        err = (r.stderr[-500:] if r else "no code produced")
        code = _gen(c, p["prompt"], extra=(
            f"\n\nYour previous attempt:\n```python\n{code}\n```\nfailed the tests with:\n{err}\n"
            "Fix it and return the COMPLETE corrected function."))
    return _passes(code, p)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "single"
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4-flash"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 164
    RES.mkdir(exist_ok=True)
    probs = load(n)
    fn = solve_single if mode == "single" else solve_ultracode
    ok = done = 0
    with ThreadPoolExecutor(max_workers=8 if mode == "single" else 5) as ex:
        futs = [ex.submit(fn, model, p) for p in probs]
        for f in as_completed(futs):
            try:
                ok += int(bool(f.result()))
            except Exception:
                pass
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(probs)} ... {ok} pass", flush=True)
    acc = ok / len(probs)
    print(f"\n=== HumanEval {mode} {model}: pass@1 = {ok}/{len(probs)} = {acc:.3f} ===", flush=True)
    (RES / f"humaneval_{mode}_{model}.json").write_text(json.dumps({"pass": ok, "n": len(probs), "acc": acc}))


if __name__ == "__main__":
    main()
