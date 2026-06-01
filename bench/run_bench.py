"""A/B benchmark: raw deepseek-v4-pro (baseline) vs the ultracode harness.

For each planted-bug task we run both conditions and score recall / precision /
spurious against known ground truth. Ultracode is scored on its SURVIVORS (the
verified output it actually stands behind) — the fair "what does it report" — and
also on all pre-verification findings (discovery breadth). Writes a JSON blob and
a markdown report under bench/results/.

Usage:  python bench/run_bench.py [--tasks auth,web] [--out bench/results/run1]
"""

import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.config import UltracodeConfig
from ultracode.harness import run as ultracode_run
from ultracode.schema import VerifyLens
from bench.baseline import baseline_find
from bench.deepseek_client import DeepSeekClient
from bench.scorer import aggregate, score
from bench.tasks import ALL_TASKS, total_planted
from bench.large_task import BUG_TASK as _LARGE, BUG_TASK_LARGE2 as _LARGE2
from bench.real_task import REAL_TASK as _REAL, AVAILABLE as _REAL_OK

_POOL = ALL_TASKS + [_LARGE, _LARGE2] + ([_REAL] if _REAL_OK else [])


def _cfg() -> UltracodeConfig:
    return UltracodeConfig(
        verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES],
        max_finders=4, max_children=8, verify_quorum=2, concurrency=24,
        discovery_dry_rounds=2, discovery_max_rounds=3,
        reactive_replan=True, voi_verify=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--out", default="bench/results/run")
    ap.add_argument("--model", default="deepseek-v4-pro")
    ap.add_argument("--force", action="store_true", help="force full orchestration (bypass discernment) for A/B")
    args = ap.parse_args()

    tasks = _POOL
    if args.tasks:
        want = set(args.tasks.split(","))
        tasks = [t for t in _POOL if t.id in want]

    rows = []
    base_scores, ultra_surv_scores, ultra_all_scores = [], [], []
    base_usage_tot = {"total_tokens": 0, "calls": 0}
    ultra_usage_tot = {"total_tokens": 0, "calls": 0}

    for task in tasks:
        print(f"\n### TASK {task.id} ({len(task.planted)} planted) ###", flush=True)

        # --- baseline ---
        cb = DeepSeekClient(model=args.model)
        t0 = time.time()
        bf = baseline_find(cb, task)
        bt = time.time() - t0
        bs = score(bf, task)
        base_scores.append(bs)
        bu = cb.usage.snapshot()
        base_usage_tot["total_tokens"] += bu["total_tokens"]; base_usage_tot["calls"] += bu["calls"]
        print(f"  baseline:  recall={bs.recall:.2f} prec={bs.precision:.2f} findings={bs.n_findings} "
              f"spurious={bs.spurious} | {bu['total_tokens']}tok {bt:.0f}s", flush=True)

        # --- ultracode ---
        cu = DeepSeekClient(model=args.model, max_workers=24)  # scale: many skeptics in flight
        t0 = time.time()
        res = ultracode_run(
            task.prompt, context=task.code,
            delegate_fn=cu.delegate_fn, aux_call_fn=cu.aux_call_fn,
            config=_cfg(), force_orchestrate=(True if args.force else None), run_id=f"bench-{task.id}",
        )
        ut = time.time() - t0
        us = score(res.survivors, task)       # what ultracode stands behind (verified)
        ua = score(res.findings, task)        # discovery breadth (pre-verify)
        ultra_surv_scores.append(us); ultra_all_scores.append(ua)
        uu = cu.usage.snapshot()
        ultra_usage_tot["total_tokens"] += uu["total_tokens"]; ultra_usage_tot["calls"] += uu["calls"]
        print(f"  ultracode: recall={us.recall:.2f} prec={us.precision:.2f} survivors={len(res.survivors)} "
              f"(found {ua.recall:.2f} pre-verify, {len(res.findings)} raw) | {uu['total_tokens']}tok {ut:.0f}s", flush=True)

        rows.append({
            "task": task.id, "planted": len(task.planted), "near_clean": task.near_clean,
            "baseline": {**bs.as_dict(), "tokens": bu["total_tokens"], "seconds": round(bt, 1)},
            "ultracode_survivors": {**us.as_dict(), "tokens": uu["total_tokens"], "seconds": round(ut, 1)},
            "ultracode_all_findings": ua.as_dict(),
            "ultracode_stages": res.stages,
            "ultracode_caps": res.caps_announced,
            "ultracode_answer": res.answer[:2000],
        })

    result = {
        "model": args.model,
        "total_planted": sum(len(t.planted) for t in tasks),
        "baseline_agg": aggregate(base_scores),
        "ultracode_survivors_agg": aggregate(ultra_surv_scores),
        "ultracode_all_agg": aggregate(ultra_all_scores),
        "baseline_tokens": base_usage_tot, "ultracode_tokens": ultra_usage_tot,
        "rows": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(result, indent=2))
    _write_report(result, out.with_suffix(".md"))
    print("\n=== SUMMARY ===")
    print("baseline   :", result["baseline_agg"])
    print("ultracode  :", result["ultracode_survivors_agg"], "(survivors)")
    print("ultra(all) :", result["ultracode_all_agg"], "(pre-verify)")
    print(f"cost: baseline {base_usage_tot['total_tokens']}tok vs ultracode {ultra_usage_tot['total_tokens']}tok")
    print("report:", out.with_suffix(".md"))


def _write_report(r, path):
    b, us, ua = r["baseline_agg"], r["ultracode_survivors_agg"], r["ultracode_all_agg"]
    lines = [
        f"# Ultracode benchmark — {r['model']}", "",
        f"Baseline = raw single-shot {r['model']}. Ultracode = the harness (decompose → fan-out → "
        "adversarially verify → loop-until-dry → synthesize) driving the same model.", "",
        "## Headline", "",
        "| metric | baseline | ultracode (verified) | ultracode (pre-verify) |",
        "|---|---|---|---|",
        f"| overall recall | {b.get('overall_recall')} | {us.get('overall_recall')} | {ua.get('overall_recall')} |",
        f"| mean precision | {b.get('mean_precision')} | {us.get('mean_precision')} | {ua.get('mean_precision')} |",
        f"| total findings | {b.get('total_findings')} | {us.get('total_found','?')} reported | {ua.get('total_findings')} raw |",
        f"| total spurious | {b.get('total_spurious')} | {us.get('total_spurious')} | {ua.get('total_spurious')} |",
        f"| tokens | {r['baseline_tokens']['total_tokens']} | {r['ultracode_tokens']['total_tokens']} | — |",
        "", "## Per task", "",
        "| task | planted | baseline R/P | ultracode R/P (survivors) | ultra found pre-verify |",
        "|---|---|---|---|---|",
    ]
    for row in r["rows"]:
        bl, ul, al = row["baseline"], row["ultracode_survivors"], row["ultracode_all_findings"]
        lines.append(f"| {row['task']}{'*' if row['near_clean'] else ''} | {row['planted']} | "
                     f"{bl['recall']}/{bl['precision']} | {ul['recall']}/{ul['precision']} | {al['recall']} |")
    lines += ["", "_* near-clean task: precision (not flooding nits) matters most._", ""]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
