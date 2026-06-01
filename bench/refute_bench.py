"""A/B for the adversarial layer: raw deepseek-v4-pro judging claims vs the
ultracode skeptic pool (verify.py) judging the same claims.

Headline metric: FALSE-CLAIM REFUTATION RATE — of the subtly-false claims, how
many does each method correctly call out as false. The baseline is one confident
pass; ultracode runs independent, multi-lens, default-to-refuted skeptics that
read the code (ground truth) before voting.

Usage:  python bench/refute_bench.py [--out bench/results/refute]
"""

import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultracode.adapters import extract_json
from ultracode.config import UltracodeConfig
from ultracode.schema import Finding, VerifyLens
from ultracode.verify import verify_findings
from bench.deepseek_client import DeepSeekClient
from bench.refute_tasks import CLAIM_TASKS, totals


def baseline_judge(client, task):
    numbered = "\n".join(f"{i}. {c.text}" for i, c in enumerate(task.claims))
    msgs = [
        {"role": "system", "content": "You are a rigorous code reviewer. Judge each claim strictly against the code."},
        {"role": "user", "content": (
            f"CODE:\n{task.code}\n\nCLAIMS:\n{numbered}\n\n"
            "For EACH claim decide if it is TRUE or FALSE about the code. Be rigorous; a claim is FALSE if it is "
            "even partially wrong or unsafe.\n"
            'Reply with ONLY JSON: {"judgments":[{"index":0,"verdict":"true"|"false"}]}.'
        )},
    ]
    out = client.chat(msgs, temperature=0.3, max_tokens=4000)
    text = type(client)._content(out)
    parsed = extract_json(text)
    verdicts = {}
    if isinstance(parsed, dict):
        for j in parsed.get("judgments", []):
            if isinstance(j, dict) and "index" in j:
                verdicts[int(j["index"])] = str(j.get("verdict", "true")).strip().lower()
    # judged_true = anything not explicitly 'false' (refutation must be explicit)
    return [verdicts.get(i, "true") != "false" for i in range(len(task.claims))]


def ultracode_judge(client, task, cfg):
    findings = [Finding(claim=c.text).validate() for c in task.claims]
    # claims carry no evidence -> "prove" mode: survive only if a quorum confirms.
    verify_findings(findings, context=task.code, config=cfg, survival_mode="prove",
                    lenses=cfg.verify_lenses, delegate_fn=client.delegate_fn)
    return [bool(f.survived) for f in findings]  # survived == judged TRUE


def score(task, judged_true):
    n = len(task.claims)
    correct = sum(1 for c, jt in zip(task.claims, judged_true) if jt == c.is_true)
    false_claims = [(i, c) for i, c in enumerate(task.claims) if not c.is_true]
    true_claims = [(i, c) for i, c in enumerate(task.claims) if c.is_true]
    false_refuted = sum(1 for i, c in false_claims if not judged_true[i])
    true_kept = sum(1 for i, c in true_claims if judged_true[i])
    return {
        "accuracy": round(correct / n, 3),
        "false_refute_rate": round(false_refuted / len(false_claims), 3) if false_claims else None,
        "true_keep_rate": round(true_kept / len(true_claims), 3) if true_claims else None,
        "false_refuted": false_refuted, "false_total": len(false_claims),
        "true_kept": true_kept, "true_total": len(true_claims),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="bench/results/refute")
    ap.add_argument("--model", default="deepseek-v4-pro")
    args = ap.parse_args()
    cfg = UltracodeConfig(verify_lenses=[VerifyLens.CORRECTNESS, VerifyLens.SECURITY, VerifyLens.REPRODUCES],
                          max_children=8, verify_quorum=2)

    rows, base_s, ultra_s = [], [], []
    for task in CLAIM_TASKS:
        print(f"\n### {task.id} ({len(task.claims)} claims, {sum(1 for c in task.claims if not c.is_true)} false) ###", flush=True)
        cb = DeepSeekClient(model=args.model)
        t0 = time.time(); bj = baseline_judge(cb, task); bt = time.time() - t0
        bs = score(task, bj)
        base_s.append(bs)
        print(f"  baseline:  acc={bs['accuracy']} false_refute={bs['false_refute_rate']} "
              f"({bs['false_refuted']}/{bs['false_total']}) true_keep={bs['true_keep_rate']} | {cb.usage.snapshot()['total_tokens']}tok {bt:.0f}s", flush=True)

        cu = DeepSeekClient(model=args.model)
        t0 = time.time(); uj = ultracode_judge(cu, task, cfg); ut = time.time() - t0
        us = score(task, uj)
        ultra_s.append(us)
        print(f"  ultracode: acc={us['accuracy']} false_refute={us['false_refute_rate']} "
              f"({us['false_refuted']}/{us['false_total']}) true_keep={us['true_keep_rate']} | {cu.usage.snapshot()['total_tokens']}tok {ut:.0f}s", flush=True)

        rows.append({"task": task.id, "baseline": bs, "ultracode": us,
                     "claims": [{"text": c.text, "is_true": c.is_true,
                                 "baseline_true": bj[i], "ultracode_true": uj[i]} for i, c in enumerate(task.claims)]})

    def agg(scores, key):
        vals = [s[key] for s in scores if s[key] is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    result = {
        "model": args.model, "totals": totals(),
        "baseline": {"accuracy": agg(base_s, "accuracy"), "false_refute_rate": agg(base_s, "false_refute_rate"), "true_keep_rate": agg(base_s, "true_keep_rate")},
        "ultracode": {"accuracy": agg(ultra_s, "accuracy"), "false_refute_rate": agg(ultra_s, "false_refute_rate"), "true_keep_rate": agg(ultra_s, "true_keep_rate")},
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(result, indent=2))
    print("\n=== SUMMARY (adversarial layer) ===")
    print("baseline :", result["baseline"])
    print("ultracode:", result["ultracode"])
    print("The headline is false_refute_rate: does adversarial verify catch lies the bare model accepts?")


if __name__ == "__main__":
    main()
