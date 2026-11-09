# Tasks

## 1. Agent Construction Point and Spend Tracking

- [ ] 1.1 Add `build_agent` in `src/devops_cli/ai/client/factory.py` with per-request spend tracking hook: `uv run pytest tests/ai/client/test_agent_factory.py`
- [ ] 1.2 Update `src/devops_cli/roadmap/refine/refine_investigation.py` to use `build_agent`: `uv run pytest tests/roadmap/refine/test_roadmap_refine_investigation.py`
- [ ] 1.3 Remove `GatewayRouter.build_pydantic_cascade_model` and associated tests: `uv run pytest tests/ai/test_pydantic_ai_workflows.py tests/ai/test_pydantic_ai_profiles_and_providers.py`

## 2. Refactor devops ai chat and devops ai pipeline

- [ ] 2.1 Refactor `devops ai chat` in `src/devops_cli/commands/ai.py` to use `build_agent` and event streaming: `uv run pytest tests/commands/test_ai_chat.py`
- [ ] 2.2 Delete `_stream_interactive_chat_turn` alias in `src/devops_cli/commands/ai.py`: `rg "_stream_interactive_chat_turn" src tests`
- [ ] 2.3 Refactor `devops ai pipeline` in `src/devops_cli/commands/ai.py` to run stages on pydantic-ai `Agent`: `uv run pytest tests/commands/test_ai_pipeline.py`

## 3. Delete Hand-Rolled Loop and Clean Up Modules

- [ ] 3.1 Relocate embedding definitions from `src/devops_cli/ai/agents/embeddings.py` to `src/devops_cli/ai/rag/embeddings.py`: `uv run pytest tests/ai/rag/test_embedding_models.py`
- [ ] 3.2 Delete `src/devops_cli/ai/agents/agent.py`, `runner.py`, `pipeline.py`, and `memory.py`: `test ! -f src/devops_cli/ai/agents/agent.py`
- [ ] 3.3 Remove obsolete tests of deleted loop and update surviving tests: `uv run pytest tests/commands/test_ai_cmd.py`
- [ ] 3.4 Verify removed identifiers do not exist in `src/`: `! rg "PydanticAgent|_detect_tool_intent|MultiAgentPipeline|AgentMemory" src`

## 4. Verification and Archival

- [ ] 4.1 Run OpenSpec check: `uv run devops openspec check`
- [ ] 4.2 Run CI verification: `uv run devops ci`
- [ ] 4.3 Archive change folder: `uv run devops openspec archive 2489-replace-pydanticagent-with-pydantic-ai-agent`
