# Tasks

## 1. Identifier validation rejects trailing newlines

- [x] 1.1 Write tests in `tests/test_run_store.py` asserting `get_run("abc\n")` returns `None` without globbing and in `tests/test_validation.py` asserting identifier validation rejects trailing newlines, and verify with `uv run devops ci test tests/test_run_store.py tests/test_validation.py`
- [x] 1.2 Update `get_run` in `src/devops_cli/ai/run_store.py` and identifier validation in `src/devops_cli/core/validation.py`, `src/devops_cli/telemetry/memory_profiler.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/ai/harness/skills.py`, `src/devops_cli/commands/grafana.py`, `src/devops_cli/commands/pipeline.py`, `src/devops_cli/commands/uv.py`, `src/devops_cli/commands/branches.py`, `src/devops_cli/git/operations.py`, and `src/devops_cli/k8s/template.py` to use `re.fullmatch` or `fullmatch`, and verify with `uv run devops ci test tests/test_run_store.py tests/test_validation.py`
- [x] 1.3 Run `uv run devops docs generate --sync-readme` and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
