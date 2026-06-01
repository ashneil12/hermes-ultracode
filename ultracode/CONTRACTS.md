# Fork API contracts the ultracode harness binds to

Verified against `vanilla-hermes-agent` HEAD (`main`, commit `82c36c0b6`) by a
read-only extraction sweep. Every signature below was copied from source; line
refs are anchors, not guarantees against drift — re-verify after an upstream sync.
All runtime calls are funnelled through `adapters.py` so these details live in
exactly one place.

## 1. `delegate_task` — parallel subagent fan-out
`tools/delegate_tool.py:1918`
```python
def delegate_task(goal=None, context=None, toolsets=None, tasks=None,
                  max_iterations=None, acp_command=None, acp_args=None,
                  role=None, parent_agent=None) -> str   # returns a JSON STRING
```
- **Batch mode**: `tasks=[{goal, context?, toolsets?, role?}, ...]`. Returns
  `{"results":[{task_index,status,summary,api_calls,duration_seconds,model,
  exit_reason,tokens:{input,output},tool_trace,[error],[stale_paths]}], "total_duration_seconds"}`.
- `status ∈ {completed, failed, error, timeout, interrupted}`. `summary` is the
  child's `final_response`.
- **CAP**: `len(tasks)` must be `≤ delegation.max_concurrent_children` (default 3)
  or it errors → `adapters.delegate_fanout` chunks into waves.
- **Depth**: `delegation.max_spawn_depth` (default **1**). `role="orchestrator"`
  silently degrades to `leaf` at the depth floor → **route verifiers as a sibling
  fan-out, not nested delegation**.
- Children's toolsets are intersected with parent's and stripped of
  `{delegation, clarify, memory, code_execution}`.
- **Thread-safety**: `_build_child_agent` must run on the main thread; the
  process-global `model_tools._last_resolved_tool_names` is saved/restored around
  construction. We never call delegate concurrently with itself.
- `parent_agent` is injected by the runtime, never by the model.

## 2. `call_llm` — bounded, tools-off LLM call (plan / verify / synth / critic)
`agent/auxiliary_client.py:4602`
```python
def call_llm(task=None, *, provider=None, model=None, base_url=None, api_key=None,
             main_runtime=None, messages, temperature=None, max_tokens=None,
             tools=None, timeout=None, extra_body=None) -> resp
# text = resp.choices[0].message.content
```
- Async twin: `async_call_llm(...)` (same signature/semantics).
- **Thread-safety landmine**: routing uses process-local globals
  (`_RUNTIME_MAIN_PROVIDER/_MODEL`). **Do NOT call from concurrent threads.**
  Concurrent verification therefore goes through `delegate_fanout` (sibling
  subagents) or a single asyncio loop with `async_call_llm`.
- Pass `main_runtime={model,provider,base_url,api_key,api_mode}` from the live
  agent (`adapters.runtime_from_agent`) to follow the user's configured model.

## 3. Reasoning-effort plumbing
`hermes_constants.py:284`
```python
VALID_REASONING_EFFORTS = ("minimal","low","medium","high","xhigh")
parse_reasoning_effort(effort) -> {"enabled":True,"effort":<lvl>} | {"enabled":False} | None
```
- `AIAgent.__init__(reasoning_config=...)` sets `agent.reasoning_config`.
- **`run_conversation()` takes NO per-call reasoning_config** — it uses
  `agent.reasoning_config`. To force xhigh on a turn: set it on the agent before
  the turn (snapshot/restore), or build children with it via `delegation.reasoning_effort`.

## 4. Anthropic effort → thinking
`agent/anthropic_adapter.py:65`
- `ADAPTIVE_EFFORT_MAP`: `{max→max, xhigh→xhigh, high→high, medium→medium, low→low, minimal→low}`.
- `THINKING_BUDGET` (pre-4.6 manual): `{xhigh:32000, high:16000, medium:8000, low:4000}`.
- Model gates: `_ADAPTIVE_THINKING_SUBSTRINGS = ("4-6","4.6","4-7","4.7")`,
  `_XHIGH_EFFORT_SUBSTRINGS = ("4-7","4.7")`. 4.6 downgrades `xhigh→max`.
- ⚠️ **ACTION (Phase 0)**: these substrings do **not** include `4-8/4.8`. If this
  Hermes runs **Opus 4.8**, xhigh thinking won't engage until `"4-8","4.8"` are
  added to both tuples (or upstream already did — re-check after sync). On
  non-Anthropic providers (OpenRouter/Kimi/Gemini/DeepSeek) effort is translated
  by their own provider profiles and is unaffected.

## 5. System-prompt assembly / standing-injection seam
`agent/system_prompt.py`, `agent/conversation_loop.py:848-852`, `agent/prompt_builder.py:1028`
- Three tiers: **stable** (identity, tools, skills index — cached for the
  session), **context** (`system_message` + context files like `.hermes.md`/
  `AGENTS.md` — cached), **volatile** (memory, timestamp — rebuilt per turn).
- `agent.ephemeral_system_prompt` is appended **at API-call time only** (after the
  cached prefix) → the faithful, cache-safe place for the `/ultracode` standing
  reminder. Keep it byte-stable across turns.
- **PROMPT-CACHE INVARIANT**: never mutate the cached prefix mid-session.
- Skill auto-inject: `metadata.hermes.requires_toolsets: [delegation]` → the skill
  index entry shows only when the `delegation` toolset is available
  (`_skill_should_show`). This gates the *index*, not standing behavior.

## 6. Infra helpers
- `hermes_constants.get_hermes_home() -> Path` (`HERMES_HOME` or `~/.hermes`) → run ledger root.
- `hermes_cli.config.load_config() -> dict`, `cfg_get(cfg, *keys, default=)` — nested config.
- `hermes_cli.kanban_db.create_task(conn, *, title, body, priority, parents, ...) -> task_id`,
  `list_tasks(conn, *, status, session_id, ...)` — optional durable control-plane.
- `tools.registry.registry.register(name, toolset, schema, handler, ...)` — to expose
  an ultracode tool/command (Phase 3+).

## Design consequences (baked into the harness)
1. **Concurrent verification = sibling `delegate_fanout`**, never threaded `call_llm`.
2. **Wave-chunk** any fan-out wider than `max_concurrent_children`; announce it.
3. **Standing stance** rides `ephemeral_system_prompt` (cache-safe) + a
   `requires_toolsets:[delegation]` SKILL.md; the *behavior* is enforced by this
   harness, not by the prose.
4. Drive xhigh via `reasoning_config` snapshot/restore on the agent (Phase 0/3).
