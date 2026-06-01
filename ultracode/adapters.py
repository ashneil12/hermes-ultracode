"""Dependency-injected seams over the fork's runtime.

Every call into the heavy Hermes runtime goes through here, and every entry
point accepts an injectable function (``delegate_fn`` / ``call_fn``). That gives
us two things:

1. Unit tests pass fakes and never import delegate_tool / auxiliary_client, so
   the whole cognitive layer is testable with no model and no environment.
2. There is exactly ONE place that knows the real contracts (signatures, the
   JSON-string return of delegate_task, the concurrency cap, the thread-safety
   landmine), instead of those details leaking across the package.

Contracts encoded here (verified against fork HEAD — see CONTRACTS.md):
  * tools.delegate_tool.delegate_task(tasks=[...], parent_agent, role) -> JSON str
    {"results": [{task_index,status,summary,...}], "total_duration_seconds"}.
    Errors if len(tasks) > delegation.max_concurrent_children -> we chunk waves.
  * agent.auxiliary_client.call_llm(messages=[...], tools=None, ...) -> resp,
    text at resp.choices[0].message.content. Its routing uses process-local
    globals, so it is NOT safe to call from concurrent threads — concurrent
    verification must go through delegate_fanout (sibling subagents), not
    threaded call_llm. async_call_llm is fine under a single asyncio loop.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Robust JSON extraction (replaces upstream's greedy re.search(r"{.*}")).
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> Optional[Any]:
    """Pull the first valid JSON object/array out of an LLM reply.

    Strategy, in order: (1) try the whole string; (2) try fenced ```json blocks;
    (3) scan for the first balanced {...} or [...] span and parse that; (4) a
    couple of cheap repairs (strip trailing commas). Returns None on total
    failure so callers can repair-retry rather than crash on str()-coercion.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    candidates: List[str] = [text.strip()]
    for m in _FENCE_RE.finditer(text):
        candidates.append(m.group(1).strip())
    span = _first_balanced_span(text)
    if span:
        candidates.append(span)

    for cand in candidates:
        for attempt in (cand, _strip_trailing_commas(cand)):
            try:
                return json.loads(attempt)
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def _first_balanced_span(text: str) -> Optional[str]:
    start = None
    opener = closer = ""
    for i, ch in enumerate(text):
        if ch in "{[" and start is None:
            start, opener = i, ch
            closer = "}" if ch == "{" else "]"
            depth = 0
        if start is not None and ch in "{[":
            depth += 1
        elif start is not None and ch in "}]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _strip_trailing_commas(s: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", s)


# ---------------------------------------------------------------------------
# delegate_task wrapper — parallel subagent fan-out with wave-chunking.
# ---------------------------------------------------------------------------


def delegate_fanout(
    tasks: List[Dict[str, Any]],
    *,
    parent_agent: Any = None,
    role: str = "leaf",
    max_children: int = 3,
    concurrency: Optional[int] = None,
    delegate_fn: Optional[Callable[..., str]] = None,
) -> List[Dict[str, Any]]:
    """Fan ``tasks`` out as parallel subagents, returning results ordered by a
    GLOBAL task_index.

    Two knobs, deliberately separate:
      * ``max_children`` — the backend's PER-CALL cap (the real Hermes
        ``delegate_task`` errors above ``delegation.max_concurrent_children``), so
        we split into waves of this size.
      * ``concurrency`` — how many tasks may be IN FLIGHT at once. When it
        exceeds ``max_children`` we dispatch multiple waves CONCURRENTLY, so a
        backend that caps each call at 3 can still run 100 agents at once.

    ⚠️ Concurrent waves call ``delegate_fn`` from multiple threads. The REAL
    Hermes ``delegate_task`` is NOT safe under that (it mutates the process-global
    ``model_tools._last_resolved_tool_names`` — see CONTRACTS.md §1), so against
    that backend leave ``concurrency`` unset (sequential waves). Concurrency-safe
    backends (the DeepSeek bench client; a fixed Hermes core) get true scale.
    Raising real-Hermes parallelism past the per-call cap is the upstream fix this
    surfaces.
    """
    if not tasks:
        return []
    fn = delegate_fn or _real_delegate_task
    cap = max(1, int(max_children))
    waves = [(base, tasks[base : base + cap]) for base in range(0, len(tasks), cap)]

    def run_wave(base_wave):
        base, wave = base_wave
        try:
            parsed = _parse_delegate_result(fn(tasks=wave, parent_agent=parent_agent, role=role))
        except Exception as exc:
            # one wave's backend error must not crash the other 99 at scale — degrade it
            # to per-task error entries so the rest of the fan-out completes.
            return [{"task_index": base + local, "status": "error", "summary": None,
                     "error": f"delegate wave failed: {exc}"} for local in range(len(wave))]
        entries: List[Dict[str, Any]] = []
        for local in range(len(wave)):
            entry = parsed[local] if local < len(parsed) and isinstance(parsed[local], dict) else None
            if entry is None:
                entries.append({"task_index": base + local, "status": "error", "summary": None,
                                "error": "missing/invalid result for task"})
                continue
            e = dict(entry)
            li = e.get("task_index", local)
            e["task_index"] = base + (li if isinstance(li, int) and 0 <= li < len(wave) else local)
            entries.append(e)
        return entries

    if concurrency is None or concurrency <= cap or len(waves) <= 1:
        results: List[Dict[str, Any]] = []
        for w in waves:
            results.extend(run_wave(w))
    else:
        from concurrent.futures import ThreadPoolExecutor

        wave_workers = max(1, min(len(waves), -(-int(concurrency) // cap)))  # ceil(concurrency/cap)
        with ThreadPoolExecutor(max_workers=wave_workers) as ex:
            collected = list(ex.map(run_wave, waves))
        results = [e for wave_entries in collected for e in wave_entries]

    results.sort(key=lambda e: e.get("task_index", 0))
    return results


def _parse_delegate_result(raw: Any) -> List[Dict[str, Any]]:
    """delegate_task returns a JSON *string*; tolerate a pre-parsed dict too."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return [{"task_index": 0, "status": "error", "summary": None, "error": f"unparseable delegate result: {raw[:200]}"}]
    if isinstance(raw, dict):
        if "error" in raw and "results" not in raw:
            return [{"task_index": 0, "status": "error", "summary": None, "error": str(raw["error"])}]
        results = raw.get("results", [])
        return results if isinstance(results, list) else []
    if isinstance(raw, list):
        return raw
    return []


def _real_delegate_task(*, tasks: List[Dict[str, Any]], parent_agent: Any, role: str) -> str:
    # Lazy import: keeps the heavy runtime out of unit tests.
    from tools.delegate_tool import delegate_task  # type: ignore

    return delegate_task(tasks=tasks, role=role, parent_agent=parent_agent)


# ---------------------------------------------------------------------------
# auxiliary call_llm wrapper — bounded, tools-off LLM calls (plan/verify/critic).
# ---------------------------------------------------------------------------


def aux_call(
    messages: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    main_runtime: Optional[Dict[str, Any]] = None,
    call_fn: Optional[Callable[..., Any]] = None,
) -> str:
    """A constrained, tools-OFF LLM call. Returns the message content string.

    Used by the planner, the synthesis step, and (single-threaded) critic.
    Tools are always None here by design — these are reasoning calls, not
    tool-using agents (delegate_fanout is the tool-using path).
    """
    fn = call_fn or _real_call_llm
    resp = fn(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=None,
        main_runtime=main_runtime,
    )
    return _content_of(resp)


def _content_of(resp: Any) -> str:
    """Normalize an OpenAI-shaped response (or a plain string fake) to text."""
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    try:
        content = resp.choices[0].message.content
        return content if isinstance(content, str) else ""
    except (AttributeError, IndexError, TypeError):
        # tolerate dict-shaped fakes
        try:
            return resp["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ""


def _real_call_llm(*, messages, model, temperature, max_tokens, tools, main_runtime):
    from agent.auxiliary_client import call_llm  # type: ignore

    kwargs: Dict[str, Any] = {"messages": messages, "tools": tools}
    if model is not None:
        kwargs["model"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if main_runtime is not None:
        kwargs["main_runtime"] = main_runtime
    return call_llm(**kwargs)


def runtime_from_agent(agent: Any) -> Optional[Dict[str, Any]]:
    """Build the ``main_runtime`` routing dict from a live AIAgent, so aux calls
    follow the same provider/model the user configured. Returns None if the
    agent doesn't expose the attributes (tests / detached use)."""
    if agent is None:
        return None
    keys = ("model", "provider", "base_url", "api_key", "api_mode")
    rt = {k: getattr(agent, k, None) for k in keys}
    return rt if rt.get("model") else None
