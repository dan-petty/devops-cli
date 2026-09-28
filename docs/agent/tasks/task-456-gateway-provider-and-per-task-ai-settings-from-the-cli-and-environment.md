# Task 456: Gateway Provider and Per-Task AI Settings From the CLI and Environment

**Issue**: [#456](https://github.com/dan-petty/devops-cli/issues/456)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/config`, `priority/p2-medium`

---

## 1. Description & Objectives

Routing a task to the LiteLLM gateway (`provider: gateway`, model `devops-coder`) was possible
only by editing `config.yaml`:
- `devops ai config --provider gateway` was rejected: its provider list omitted `gateway`, which
  the client supports.
- `devops config set ai.tasks.chat.model devops-coder` failed: `dotted_set` handled two-level
  keys only.
- `DEVOPS_CLI_AI_TASK_CHAT_*` overrides hit the same error, which `_apply_env_overrides`
  swallowed, so they were silently dropped.

### Key Deliverables Completed:

- [x] **`devops ai config`** accepts `gateway`. A new `--task` option sets provider, model, URLs,
  parallelism, API base and retries for one task (`chat`, `metadata`, `analysis`, `verification`,
  `compose`, `embedding`) instead of every call. `--task` alone shows that task's overrides.
- [x] **`dotted_set` takes keys of any depth**:
  - `ai.tasks.chat.model` walks the nested sections;
  - a field that is unset (per-task overrides default to none) is coerced by its declared type,
    so `context_window` becomes an integer and `ollama_urls` a list;
  - a key naming no field raises instead of setting nothing.
- [x] **Environment overrides apply or fail loudly**: `DEVOPS_CLI_AI_TASK_*` now apply. An
  override that cannot, such as a non-integer `DEVOPS_CLI_AI_MAX_RETRIES`, raises a
  configuration error naming the variable.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ai_task_settings_paths.py`:
    - each path sets a gateway chat task: `ai config --task`, `config set`, the environment;
    - `ai config --provider gateway`;
    - an unknown task;
    - typed nested values;
    - unknown nested keys;
    - a failing environment override.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
