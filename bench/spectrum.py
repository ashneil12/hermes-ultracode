"""Unified 4-way spectrum table across the recognized benchmarks.

Reads every result file and prints one table:
    benchmark | flash-single | flash+ultra | opus-single | opus+ultra
so the full spectrum (weak base, weak+orchestration, strong base, strong+orchestration) is visible
at a glance. Run after the flash runs, the math judge, and the Opus workflows + graders.

  python bench/spectrum.py
"""

import json
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"


def _load(name):
    p = RES / name
    return json.loads(p.read_text()) if p.is_file() else None


def _acc(d, *keys):
    if not d:
        return None
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return None
    if isinstance(d, dict):
        return d.get("acc")
    return d


def cell(v):
    return f"{v:.3f}" if isinstance(v, (int, float)) else "  –  "


def main():
    rows = []

    # GSM8K
    g_fs = _acc(_load("gsm8k_single_deepseek-v4-flash.json"), "acc")
    g_fu = _acc(_load("gsm8k_ultracode_deepseek-v4-flash.json"), "acc")
    g_op = _load("gsm8k_opus_100.json")
    g_os = (g_op["opus_base"] / g_op["n"]) if g_op else None
    g_ou = (g_op["opus_ultra"] / g_op["n"]) if g_op else None
    rows.append(("GSM8K (grade-school, n=200/100)", g_fs, g_fu, g_os, g_ou))

    # HumanEval
    h_fs = _acc(_load("humaneval_single_deepseek-v4-flash.json"), "acc")
    h_fu = _acc(_load("humaneval_ultracode_deepseek-v4-flash.json"), "acc")
    h_op = _load("humaneval_opus.json")
    rows.append(("HumanEval (code pass@1, n=164)", h_fs, h_fu,
                 _acc(h_op, "base", "acc"), _acc(h_op, "ultra", "acc")))

    # MATH-500
    m_flash = _load("math_judged_deepseek-v4-flash.json")
    m_opus = _load("math_judged_opus.json")
    rows.append(("MATH-500 (competition, n=200)",
                 _acc(m_flash, "single", "acc"), _acc(m_flash, "ultracode", "acc"),
                 _acc(m_opus, "single", "acc"), _acc(m_opus, "ultracode", "acc")))

    w = 34
    print("\n" + "=" * 78)
    print(f"{'benchmark':<{w}} {'flash':>9} {'flash+U':>9} {'opus':>9} {'opus+U':>9}")
    print("-" * 78)
    for name, fs, fu, os_, ou in rows:
        print(f"{name:<{w}} {cell(fs):>9} {cell(fu):>9} {cell(os_):>9} {cell(ou):>9}")
    print("=" * 78)
    print("flash = deepseek-v4-flash (deliberately weak).  +U = +ultracode.  opus = claude-opus.")
    print("Read the DELTAS, not the absolutes: ultracode multiplies a weak model toward the strong")
    print("baseline exactly where there is headroom (HumanEval self-repair, MATH-L5), and is a")
    print("near-wash where the single pass already saturates (GSM8K).\n")


if __name__ == "__main__":
    main()
