# Proposal

## Why

Issue #1068 reports that `ai.tasks.metadata` is declared, documented, and settable through environment variables (`DEVOPS_CLI_AI_TASK_METADATA_*`), but no code reads it.
The commands that write file and repository metadata (`devops analyze path|branch|pr --enhanced` and `devops ai agents`) currently read the global `ai` settings.
Users cannot route these batch metadata commands to background model tiers without moving all other commands that read global `ai.model`.

## What Changes

- Pass task `"metadata"` to `get_llm_client` in `devops analyze path`, `branch`, and `pr` when `--enhanced` is active.
- Pass task `"metadata"` to `get_llm_client` in `devops ai agents`.
- Update environment variable descriptions in `src/devops_cli/config/env.py` for metadata provider, model, and Ollama URLs to name the commands: "for `analyze --enhanced` and `ai agents`".
- Regenerate `docs/ENV_VARS.md` to reflect the updated descriptions.
- Add tests in `tests/test_ai_task_metadata.py` ensuring that `devops analyze path --enhanced` and `devops ai agents` route to `ai.tasks.metadata` when configured, and fall back to global `ai` settings when unset.
- This change alters observable model selection behavior for `devops analyze --enhanced` and `devops ai agents`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `ai-task-models`: Specifies AI model selection and configuration for specialized tasks including metadata generation and agent instruction synthesis.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/analyze.py`: `get_llm_client` calls in `path`, `branch`, and `pr` pass `"metadata"`.
- `src/devops_cli/commands/ai.py`: `get_llm_client` in `_generate_agents_md_with_llm` passes `"metadata"`.
- `src/devops_cli/config/env.py`: Environment variable specifications for metadata task include command references.
- `docs/ENV_VARS.md`: Introspected documentation updated via `devops docs generate --sync-readme`.
- `tests/test_ai_task_metadata.py`: Unit tests asserting metadata task model routing.

## Feasibility

- Confirmed against Python 3.14.7 runtime and devops-cli 0.2.25+.
- Verified that `settings.ai.for_task("metadata")` correctly yields task overrides for `model`, `provider`, and endpoints while preserving global defaults when unset.
- Verified that `get_llm_client("metadata", settings=settings)` delegates to `settings.ai.for_task("metadata")` and instantiates `LLMClient` with the resolved configuration.
- Verified that setting `DEVOPS_CLI_AI_TASK_METADATA_MODEL=devops-background` correctly overrides `settings.ai.tasks.metadata.model` during `load_settings()`.

## Existing Tool Considered

The codebase already provides `AITasksConfig.metadata` and `AIConfig.for_task(...)` built on Pydantic v2.
No external tool or library is required.
Wiring the existing task configuration replaces implicit use of global `ai` settings across four call sites and deletes zero public interfaces.
