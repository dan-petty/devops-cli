# Design

## Decisions

### 1. Construction function in factory.py
Add `build_agent` in `src/devops_cli/ai/client/factory.py`, alongside `get_task_model` and `get_llm_client`.
`build_agent` accepts a model instance, model name, or task string. When given a task string or None with a task keyword argument, it calls `get_task_model(task)`.
It automatically attaches a spend tracking capability using `Hooks(after_model_request=...)` that calls `track_request_spend` after each model reply.

### 2. Spend capability per model request
Instead of recording one spend record for the entire run at completion, the attached hook records one spend record per model reply. This records multi-turn and tool-using runs accurately in `devops_cli_ai_requests_total` and the SQLite spend ledger.

### 3. Interactive chat streaming and history
`devops ai chat` executes turns with `agent.run_stream_events(effective_prompt, message_history=history)`.
Thinking text streams from `ThinkingPartDelta` when `--thinking` is active. Reply text streams from `TextPartDelta`.
Tool call and tool result events print to the console.
The persistent message history updates from `event.result.all_messages()` at the end of each turn.

### 4. Multi-agent pipeline execution
`devops ai pipeline` creates a pydantic-ai `Agent` for each stage persona with its persona tools.
Each stage receives the prompt and previous stage outputs, and runs offline or online without the deleted `MultiAgentPipeline` class.

### 5. Module cleanup and relocation
- Delete `src/devops_cli/ai/agents/agent.py`, `runner.py`, `pipeline.py`, and `memory.py`.
- Keep `src/devops_cli/ai/agents/context.py` and `tools.py` for shared type definitions (`Tool`, `AbstractToolset`, `FunctionToolset`).
- Move embedding types from `src/devops_cli/ai/agents/embeddings.py` to `src/devops_cli/ai/rag/embeddings.py`.
- Delete `GatewayRouter.build_pydantic_cascade_model`.

## Rejected alternatives

### Keep hand-rolled tool parser in PydanticAgent
Rejected: The hand-rolled loop in `runner.py` uses fragile text regex parsing (`_detect_tool_intent`) rather than structured tool calling provided natively by modern LLM APIs and pydantic-ai.

### Separate builder module under ai/agents/
Rejected: The change deletes most modules in `ai/agents/`. Placing `build_agent` in `src/devops_cli/ai/client/factory.py` keeps client and model creation logic in one cohesive factory module.

### Record spend once per run
Rejected: Multi-turn tool execution runs make multiple distinct model requests. Aggregating them into one record loses per-request token granularity and delays spend visibility.
