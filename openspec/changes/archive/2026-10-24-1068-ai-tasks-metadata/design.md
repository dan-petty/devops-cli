# Design

## Context

`ai.tasks.metadata` was declared in `AITasksConfig` alongside `chat`, `analysis`, and `embedding`.
Options and environment variables (`DEVOPS_CLI_AI_TASK_METADATA_*`) were configured, but callers in `devops analyze --enhanced` and `devops ai agents` did not pass the task name when requesting an LLM client.
Consequently, requests used global `ai` settings instead of the metadata task overrides.

## Goals / Non-Goals

**Goals:**

- Ensure `devops analyze path|branch|pr --enhanced` builds its LLM client from `settings.ai.for_task("metadata")`.
- Ensure `devops ai agents` builds its LLM client from `settings.ai.for_task("metadata")`.
- Preserve fallback to global `ai` configuration when `ai.tasks.metadata` is unset.
- Document that metadata task environment variables apply to `analyze --enhanced` and `ai agents`.
- Verify behavior with fast, offline tests running in under 1 second.

**Non-Goals:**

- Do not alter `devops review` pre-analysis, which performs deterministic analysis without model calls.
- Do not add new configuration keys or change defaults.
- Do not add a table row for `DEVOPS_CLI_AI_TASK_METADATA_REASONING_EFFORT`, which is tracked separately in #956.

## Decisions

- **Wire the existing `ai.tasks.metadata` task setting rather than deleting it.**
  - *Rejected Alternative:* Delete `ai.tasks.metadata`. Evidence: Deleting the setting forces batch metadata commands onto the global model tier, preventing users from routing long-running batch extraction jobs to slow or background tiers via `config.yaml`.
- **Pass task name `"metadata"` to `get_llm_client`.** `get_llm_client("metadata", settings=settings)` calls `settings.ai.for_task("metadata")` internally and resolves API keys and cache settings consistently.
  - *Rejected Alternative:* Construct `LLMClient(config=settings.ai.for_task("metadata"))` directly at each call site. Evidence: Bypasses API key resolution and client override interception used across tests and tools.
- **Route `devops ai agents` to the metadata task.**
  - *Rejected Alternative:* Introduce a separate `ai.tasks.agents` task configuration. Evidence: Both `analyze --enhanced` and `ai agents` are batch repository metadata tasks targeting background model tiers. Adding a single-use task slot increases configuration complexity without operational benefit.

## Risks / Trade-offs

- [Users with explicit `ai.tasks.metadata` in `config.yaml` will see those settings take effect] → This matches user intent and fixes the defect where those settings were silently ignored.
