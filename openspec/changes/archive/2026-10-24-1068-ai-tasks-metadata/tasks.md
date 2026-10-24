# Tasks

## 1. Metadata task model routing for analyze and agents

- [x] 1.1 Write failing tests in `tests/test_ai_task_metadata.py` verifying that `devops analyze path --enhanced` and `devops ai agents` route to `ai.tasks.metadata.model` when set and fall back to global `ai.model` when unset, and verify failure on current code with `uv run devops ci test tests/test_ai_task_metadata.py`
- [x] 1.2 Update `commands/analyze.py` (`path`, `branch`, `pr`) and `commands/ai.py` (`agents`) to initialize their LLM clients using `settings.ai.for_task("metadata")` via `get_llm_client("metadata", settings=settings)`
- [x] 1.3 Run `uv run devops ci test tests/test_ai_task_metadata.py` and verify that the tests pass

## 2. Environment variable specifications and documentation

- [x] 2.1 Update descriptions for metadata environment variables in `src/devops_cli/config/env.py` to name the commands: "for `analyze --enhanced` and `ai agents`"
- [x] 2.2 Synchronize documentation with `uv run devops docs generate --sync-readme`
- [x] 2.3 Verify all gates pass with `uv run devops openspec check`, `uv run devops docs check`, and `uv run devops ci fail-to-pass --base origin/main`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
