"""DeepSeek backend for the ultracode harness benchmark.

Implements the two DI seams harness.run() needs — ``delegate_fn`` (parallel
subagent fan-out) and ``aux_call_fn`` (tools-off plan/critic/synthesize) — as
real calls to deepseek-v4-pro via the OpenAI SDK (DeepSeek is OpenAI-compatible).
The SDK gives us connection pooling, timeouts, and retry/backoff that raw urllib
lacked (the first smoke run died on a mid-stream IncompleteRead from the long
reasoning generation — the SDK handles that).

The whole point: drive the ultracode orchestration with a model markedly weaker
than the orchestrator that designed it, so any laziness in the instructions is
exposed — the weak model simply won't comply with vague prompts.
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI


def _load_env() -> Dict[str, str]:
    env = {}
    p = Path.home() / ".ultracode-bench" / "deepseek.env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


_WORKER_SYSTEM = (
    "You are a focused expert worker inside an investigation harness. Follow the instructions in the "
    "message EXACTLY. Be concrete and specific; never pad with speculation. When the instructions ask "
    "for JSON, reply with ONLY valid JSON and nothing else — no prose, no markdown fences."
)


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, pt: int, ct: int):
        with self._lock:
            self.calls += 1
            self.prompt_tokens += pt
            self.completion_tokens += ct

    def err(self):
        with self._lock:
            self.errors += 1

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return {
                "calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens,
                "errors": self.errors,
            }


class DeepSeekClient:
    def __init__(self, model: str = "deepseek-v4-pro", *, max_workers: int = 6, timeout: float = 240.0, retries: int = 4):
        env = _load_env()
        api_key = env.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
        base_url = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not found in ~/.ultracode-bench/deepseek.env")
        self.model = model
        self.max_workers = max_workers
        self.usage = Usage()
        self._client = OpenAI(api_key=api_key, base_url=f"{base_url}/v1", timeout=timeout, max_retries=retries)

    # ---- low-level completion (returns OpenAI response object) ------------
    def chat(self, messages, *, model=None, temperature=None, max_tokens=None):
        kwargs: Dict[str, Any] = {"model": model or self.model, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        # deepseek-v4-pro is a REASONING model: completion_tokens includes
        # reasoning_tokens, so a tight max_tokens gets eaten by thinking and
        # truncates the actual output (silently breaking JSON parsing). Floor it.
        kwargs["max_tokens"] = max(int(max_tokens), 4000) if max_tokens else 4000
        try:
            resp = self._client.chat.completions.create(**kwargs)
            u = getattr(resp, "usage", None)
            if u:
                self.usage.add(int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0))
            return resp
        except Exception:
            self.usage.err()
            return None

    @staticmethod
    def _content(resp) -> str:
        if resp is None:
            return ""
        try:
            return resp.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            return ""

    # ---- DI seam: aux_call_fn (tools-off) --------------------------------
    def aux_call_fn(self, **kwargs):
        return self.chat(
            kwargs["messages"],
            model=kwargs.get("model"),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
        )

    # ---- DI seam: delegate_fn (parallel subagent fan-out) ----------------
    def delegate_fn(self, *, tasks: List[Dict[str, Any]], parent_agent: Any = None, role: str = "leaf") -> str:
        def one(idx_task):
            i, t = idx_task
            t0 = time.time()
            resp = self.chat(
                [{"role": "system", "content": _WORKER_SYSTEM}, {"role": "user", "content": t["goal"]}],
                temperature=0.4, max_tokens=4000,
            )
            content = self._content(resp)
            status = "completed" if content else "error"
            u = getattr(resp, "usage", None) if resp is not None else None
            return {
                "task_index": i,
                "status": status,
                "summary": content if content else None,
                "api_calls": 1,
                "duration_seconds": round(time.time() - t0, 2),
                "model": self.model,
                "exit_reason": "completed" if content else "error",
                "tokens": {"input": int(getattr(u, "prompt_tokens", 0) or 0) if u else 0,
                           "output": int(getattr(u, "completion_tokens", 0) or 0) if u else 0},
                "tool_trace": [],
                "error": None if content else "empty/failed completion",
            }

        results: List[Optional[Dict[str, Any]]] = [None] * len(tasks)
        workers = max(1, min(self.max_workers, len(tasks)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(one, (i, t)) for i, t in enumerate(tasks)]
            for fut in as_completed(futs):
                entry = fut.result()
                results[entry["task_index"]] = entry
        return json.dumps({"results": results, "total_duration_seconds": 0.0})
