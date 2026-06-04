"""Equivalence judge for MATH-500 boxed answers.

MATH answers are LaTeX, so exact string match under-counts (\\frac{1}{2} == 0.5 == \\dfrac12).
Two-tier scoring, cheap-first:
  1. normalize both sides and compare (handles ~90% — whitespace, \\left/\\right, \\dfrac, %, $, units)
  2. only for the residual mismatches, ask an LLM "are these mathematically equal? YES/NO"
Reports accuracy overall and by difficulty level (1..5).

  python bench/math_judge.py                     # judges math_single + math_ultracode (flash)
  python bench/math_judge.py opus                # judges math_single_opus + math_ultracode_opus
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.deepseek_client import DeepSeekClient

RES = Path(__file__).resolve().parent / "results"


def _norm(s):
    s = (s or "").strip()
    # strip $..$, \boxed wrappers, \text{...}, spacing macros
    s = s.replace("$", "").replace("\\!", "").replace("\\,", "").replace("\\ ", "")
    s = re.sub(r"\\boxed\s*{(.*)}", r"\1", s)
    s = re.sub(r"\\text(?:rm|normal)?\s*{([^}]*)}", r"\1", s)
    s = re.sub(r"\\(left|right|big|Big|bigg|Bigg)\b", "", s)
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac").replace("\\cdot", "*")
    s = s.replace("\\%", "").replace("%", "").replace("^\\circ", "").replace("^{\\circ}", "")
    s = s.replace("\\degree", "").replace("{}", "").replace(" ", "")
    s = s.replace("\\le", "<=").replace("\\ge", ">=").replace("\\pi", "pi")
    # \frac{a}{b} -> a/b ; \sqrt{x} -> sqrt(x)
    s = re.sub(r"\\frac{([^{}]*)}{([^{}]*)}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt{([^{}]*)}", r"sqrt(\1)", s)
    s = s.replace("\\", "").rstrip(".").rstrip()
    # numeric canonicalization
    try:
        return str(int(float(s))) if float(s) == int(float(s)) else str(round(float(s), 6))
    except ValueError:
        return s.lower()


def _quick(boxed, gt):
    if _norm(boxed) == _norm(gt):
        return True
    # set/tuple order-insensitive compare
    a, b = _norm(boxed), _norm(gt)
    if {c for c in a if c.isalnum()} == {c for c in b if c.isalnum()} and ("," in a or "," in b):
        if sorted(re.split(r"[,;]", a)) == sorted(re.split(r"[,;]", b)):
            return True
    return None  # undecided -> LLM


def _llm_equal(client, boxed, gt):
    msg = [{"role": "system", "content": "You judge whether two math answers are EQUAL. "
            "Reply with exactly YES or NO."},
           {"role": "user", "content": f"Answer A: {boxed}\nAnswer B (ground truth): {gt}\n"
            "Are they mathematically equivalent? YES or NO."}]
    out = type(client)._content(client.chat(msg, temperature=0, max_tokens=4)).strip().upper()
    return out.startswith("Y")


def judge(tag):
    path = RES / f"math_{tag}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    client = DeepSeekClient(model="deepseek-v4-flash", max_workers=4)
    by_level = {}
    correct = total = llm_used = 0
    for i, rec in data.items():
        boxed, gt, lvl = rec["boxed"], rec["gt"], rec.get("level", 0)
        q = _quick(boxed, gt)
        if q is None:
            q = _llm_equal(client, boxed, gt)
            llm_used += 1
        total += 1
        correct += int(q)
        d = by_level.setdefault(lvl, [0, 0])
        d[0] += int(q); d[1] += 1
    return {"correct": correct, "n": total, "acc": round(correct / max(total, 1), 4),
            "llm_adjudicated": llm_used, "by_level": by_level}


def main():
    suffix = "_" + sys.argv[1] if len(sys.argv) > 1 else "_deepseek-v4-flash"
    print(f"\n=== MATH-500 equivalence judge ({suffix.lstrip('_')}) ===\n")
    summary = {}
    for mode in ("single", "ultracode"):
        r = judge(f"{mode}{suffix}")
        if r is None:
            print(f"  {mode}: (no answers file)"); continue
        summary[mode] = r
        levels = " ".join(f"L{k}:{v[0]}/{v[1]}" for k, v in sorted(r["by_level"].items()))
        print(f"  {mode:9s}: {r['correct']}/{r['n']} = {r['acc']:.3f}   "
              f"[{r['llm_adjudicated']} LLM-adjudicated]   {levels}")
    if "single" in summary and "ultracode" in summary:
        d = summary["ultracode"]["acc"] - summary["single"]["acc"]
        print(f"\n  ultracode - single = {d:+.3f}")
    (RES / f"math_judged{suffix}.json").write_text(json.dumps(summary, indent=1))
    print(f"\n  saved -> results/math_judged{suffix}.json")


if __name__ == "__main__":
    main()
