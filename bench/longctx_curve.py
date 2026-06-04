"""Combine the long-context sweep result files into one context-scaling curve.

Reads longctx_single / longctx_single_budget / longctx_ultracode for a model and prints the curve:
    corpus size  ->  single-pass recall (native window | bounded working set)  vs  ultracode recall.
The story is the SHAPE: a wash where the corpus fits one pass, a widening gap where it exceeds it.

  python bench/longctx_curve.py [deepseek-v4-flash]
"""

import json
import sys
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"


def _rows(tag, model):
    p = RES / f"longctx_{tag}_{model}.json"
    if not p.is_file():
        return {}
    return {r["n_docs"]: r for r in json.loads(p.read_text())["rows"]}


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash"
    native = _rows("single", model)
    budget = _rows("single_budget", model)
    ultra = _rows("ultracode", model)
    sizes = sorted(set(native) | set(budget) | set(ultra))

    def cell(d, n):
        r = d.get(n)
        return f"{r['recall']:.2f} ({r['found']}/{r['gt']})" if r else "    –    "

    print("\n" + "=" * 82)
    print(f"  long-context multi-value retrieval — {model}   (recall = codes recovered / planted)")
    print("-" * 82)
    print(f"  {'corpus (docs)':<16}{'single: native':>18}{'single: bounded':>18}{'ultracode':>18}")
    print("-" * 82)
    for n in sizes:
        print(f"  {n:<4d} docs       {cell(native, n):>18}{cell(budget, n):>18}{cell(ultra, n):>18}")
    print("=" * 82)
    print("  native  = full corpus in one pass (the model's raw long-context window)")
    print("  bounded = one pass under a declared 6k-token working set (the agent-turn regime)")
    print("  ultracode = chunk -> fan out one extractor per section -> reconcile the union")
    print()
    print("  Read the SHAPE: where the corpus fits one pass it is a wash (route to solo — discernment);")
    print("  where it exceeds the pass, single-pass recall collapses toward (budget / corpus) while")
    print("  ultracode holds ~1.0. The gap is the orchestration value, and it GROWS with the corpus.\n")


if __name__ == "__main__":
    main()
