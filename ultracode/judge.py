"""judge.py — the judge-panel shape for GENERATIVE tasks.

Find-then-verify is wrong for creative/open-ended work; the doctrine's shape there
is: generate N independent attempts from DIFFERENT angles, score them with
independent judges, then synthesize the winner while grafting the best survivable
ideas from the runners-up. More candidates make a blander pick, so the funnel is
throttled (cover the stance-space with a few seeds, not many).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ultracode.adapters import aux_call, delegate_fanout, extract_json, runtime_from_agent
from ultracode.config import UltracodeConfig

_ANGLES = [
    "the most direct, simplest approach that fully solves it",
    "a bold, contrarian approach that challenges the obvious framing",
    "the most rigorous and thorough approach, leaving no gap",
    "a user/empathy-first approach centered on who consumes this",
    "an elegant, minimal approach that does more with less",
]


@dataclass
class JudgeResult:
    answer: str = ""
    winner_angle: str = ""
    scores: List[dict] = field(default_factory=list)
    candidates: List[dict] = field(default_factory=list)


def judge_panel(
    task: str,
    *,
    context: str = "",
    n: int = 4,
    delegate_fn: Optional[Callable[..., str]] = None,
    aux_call_fn: Optional[Callable[..., Any]] = None,
    config: Optional[UltracodeConfig] = None,
    agent: Any = None,
    model: Optional[str] = None,
) -> JudgeResult:
    cfg = config or UltracodeConfig()
    rt = runtime_from_agent(agent)
    angles = _ANGLES[: max(2, min(n, len(_ANGLES)))]

    # 1. generate N candidates from DIFFERENT angles (parallel)
    gen_tasks = [{"goal": f"Produce a COMPLETE candidate answer/artifact for the task, committing fully to THIS "
                          f"stance: {a}.\n\nTASK:\n{task}\n{context}\n\nReturn only the candidate."} for a in angles]
    gen = delegate_fanout(gen_tasks, parent_agent=agent, max_children=cfg.max_children,
                          concurrency=cfg.concurrency, delegate_fn=delegate_fn)
    candidates = []
    for i, r in enumerate(gen):
        if isinstance(r, dict) and r.get("status") == "completed" and (r.get("summary") or "").strip():
            candidates.append({"angle": angles[i], "text": r["summary"].strip()})
    if not candidates:
        # degrade to a single solo attempt
        sol = aux_call([{"role": "system", "content": "Produce the best answer you can."},
                        {"role": "user", "content": f"{task}\n{context}"}],
                       model=model, temperature=0.5, max_tokens=2500, main_runtime=rt, call_fn=aux_call_fn)
        return JudgeResult(answer=sol, winner_angle="solo")

    # 2. score each candidate with an independent judge (parallel)
    judge_tasks = [{"goal": f"Score this candidate for the task on 0-10 (correctness, completeness, clarity, "
                            f"originality combined). Be a discerning critic.\n\nTASK:\n{task}\n\nCANDIDATE "
                            f"({c['angle']}):\n{c['text']}\n\nReply ONLY JSON: "
                            '{"score": <0-10>, "strengths": ["..."], "weaknesses": ["..."]}'}
                   for c in candidates]
    judged = delegate_fanout(judge_tasks, parent_agent=agent, max_children=cfg.max_children,
                             concurrency=cfg.concurrency, delegate_fn=delegate_fn)
    scores = []
    for i, r in enumerate(judged):
        parsed = extract_json(r.get("summary") or "") if isinstance(r, dict) else None
        sc = float(parsed.get("score", 5)) if isinstance(parsed, dict) else 5.0
        scores.append({"angle": candidates[i]["angle"], "score": sc,
                       "strengths": (parsed or {}).get("strengths", []) if isinstance(parsed, dict) else []})

    order = sorted(range(len(candidates)), key=lambda i: -scores[i]["score"])
    winner = candidates[order[0]]
    runners = [candidates[i] for i in order[1:3]]

    # 3. synthesize: spine = winner, graft the best survivable ideas from runners-up
    runner_block = "\n\n".join(f"RUNNER-UP ({c['angle']}):\n{c['text'][:1500]}" for c in runners) or "(none)"
    answer = aux_call(
        [{"role": "system", "content": "You are the synthesizer. Take the winning candidate as the SPINE; graft "
          "only the runner-up ideas that don't fight it. Don't average — produce one coherent, strong artifact."},
         {"role": "user", "content": f"TASK:\n{task}\n\nWINNER ({winner['angle']}):\n{winner['text']}\n\n{runner_block}\n\n"
          "Produce the final, best version."}],
        model=model, temperature=0.4, max_tokens=3000, main_runtime=rt, call_fn=aux_call_fn,
    )
    return JudgeResult(answer=answer, winner_angle=winner["angle"], scores=scores, candidates=candidates)
