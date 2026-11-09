# Proposal: #2489

## Why

Two agent runtimes run in the project:
1. The hand-rolled `PydanticAgent` loop (`src/devops_cli/ai/agents/agent.py`, `runner.py`, `pipeline.py`, `memory.py`) parses tool intent from model text and catches every exception.
2. The native pydantic-ai `Agent` runs the refine investigation (`src/devops_cli/roadmap/refine/refine_investigation.py`).

Issue #2489 replaces `PydanticAgent` with pydantic-ai `Agent`. It adds one construction function in `src/devops_cli/ai/client/factory.py` with per-request spend tracking, migrates `devops ai chat` and `devops ai pipeline` to the native agent runtime, and deletes the hand-rolled loop.

Closes #2489.

## What Changes

- Add `build_agent` in `src/devops_cli/ai/client/factory.py` with a per-request spend capability that calls `track_request_spend` after each model reply.
- Migrate `src/devops_cli/roadmap/refine/refine_investigation.py` to use `build_agent`.
- Migrate `devops ai chat` in `src/devops_cli/commands/ai.py` to use `build_agent` with event streaming (`run_stream_events`) and message history.
- Remove `_stream_interactive_chat_turn` alias from `src/devops_cli/commands/ai.py`.
- Migrate `devops ai pipeline` in `src/devops_cli/commands/ai.py` to use `build_agent`.
- Delete the hand-rolled loop modules: `src/devops_cli/ai/agents/agent.py`, `runner.py`, `pipeline.py`, and `memory.py`.
- Move `src/devops_cli/ai/agents/embeddings.py` definitions (`Embedder`, `EmbeddingCost`, `EmbeddingResult`, `EngineEmbeddingModel`) into `src/devops_cli/ai/rag/embeddings.py`.
- Delete unused `GatewayRouter.build_pydantic_cascade_model` in `src/devops_cli/ai/gateway.py`.
- Remove tests of the deleted hand-rolled loop and update surviving tests to use public interfaces and edge fakes.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- CLI commands `devops ai chat` and `devops ai pipeline` use native pydantic-ai agent execution with native tool calling and token spend tracking per model request.
- No `PydanticAgent`, `_detect_tool_intent`, `MultiAgentPipeline`, or `AgentMemory` symbols remain in `src/`.
- No `build_pydantic_cascade_model` or `_stream_interactive_chat_turn` symbols remain in `src/` or `tests/`.

## Feasibility

- Pydantic-AI 2.59.0 provides native `Agent`, `run_stream_events`, `ThinkingPartDelta`, `TextPartDelta`, and `Hooks(after_model_request=...)`.
- `track_request_spend` in `src/devops_cli/ai/spend/ledger.py` records token spend into the ledger and emits OpenTelemetry metrics.
- `TestModel` and `FunctionModel` enable offline verification without network access.

## Existing Tool Considered

- Pydantic-AI (`Agent`, `Hooks`, `run_stream_events`) covers agent loop orchestration, tool execution, and event streaming.
- Reusing pydantic-ai eliminates maintaining a custom tool parser and hand-rolled loop.
