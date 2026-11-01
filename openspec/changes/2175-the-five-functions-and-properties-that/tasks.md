# Tasks

## 1. Delete the two dead reasoning properties

Reads: `src/devops_cli/ai/client/streaming.py` (lines 140-210), `src/devops_cli/ai/thinking_stream.py` (lines 325-395). Changes: the same two files.

- [x] 1.1 Run `git grep -n -w thinking_detected -- src tests docs` and `git grep -n -w unique_thinking -- src tests docs`. On the base each prints only its definition line. This pair of commands is the check of the group: after the deletion both print nothing
- [x] 1.2 Delete the `thinking_detected` property from `StreamingTokenProcessor` in `src/devops_cli/ai/client/streaming.py`. Keep `has_reasoning`, which other code reads
- [x] 1.3 Delete the `unique_thinking` property from `ThinkingStreamProcessor` in `src/devops_cli/ai/thinking_stream.py`. Keep the import of `unique_lines`, which line 390 uses
- [x] 1.4 Run the two `git grep` commands of task 1.1 (both print nothing), then `uv run devops ci test tests/ai/client/test_ai_streaming.py tests/ai/test_thinking.py` (it passes)

## 2. Delete the dead Ollama semaphore code

Reads: `src/devops_cli/ai/client/unified.py` (lines 1-30 and 155-175), `src/devops_cli/ai/client/network.py` (lines 40-50, 310-330 and 575-595). Changes: the same two files.

- [ ] 2.1 Run `git grep -n -w -e _get_ollama_semaphore -e get_ollama_semaphore -e ollama_semaphores -e ollama_sem_lock -- src tests docs`. On the base it prints the definitions and the uses in `src/devops_cli/ai/client/unified.py` and `src/devops_cli/ai/client/network.py` only, and no line of `tests/` or `docs/`. After the deletion it prints nothing
- [ ] 2.2 Delete `LLMClient._get_ollama_semaphore` and the `import threading` line from `src/devops_cli/ai/client/unified.py`
- [ ] 2.3 Delete `get_ollama_semaphore`, `ollama_semaphores` and `ollama_sem_lock` from `src/devops_cli/ai/client/network.py`, and the `with ollama_sem_lock:` block in `reset_ollama_slots`. Keep `import threading` in `src/devops_cli/ai/client/network.py`, which other code uses
- [ ] 2.4 Run the `git grep` command of task 2.1 (it prints nothing), `uv run devops ci lint` (no unused import), and `uv run devops ci test tests/ai/client` (it passes)

## 3. Delete the dead settings helper

Reads: `src/devops_cli/config/settings.py` (lines 175-215 only; the file is 77 KB). Changes: the same file.

- [ ] 3.1 Run `git grep -n -w _validation_error_key -- src tests docs`. On the base it prints only the definition line (`src/devops_cli/config/settings.py:187`). After the deletion it prints nothing
- [ ] 3.2 Delete the `_validation_error_key` function from `src/devops_cli/config/settings.py`. Keep `_format_validation_error` and the import of `ValidationError`, which other code uses
- [ ] 3.3 Run the `git grep` command of task 3.1 (it prints nothing), then `uv run devops ci test tests/config/test_settings.py` (it passes)

## 4. Delete the dead dashboard property and run the gate

Reads: `src/devops_cli/grafana/schema.py`. Changes: the same file.

- [ ] 4.1 Run `git grep -n -w grid_width -- src tests docs`. On the base it prints only the definition line (`src/devops_cli/grafana/schema.py:145`). After the deletion it prints nothing
- [ ] 4.2 Delete the `grid_width` property from `Dashboard` in `src/devops_cli/grafana/schema.py`, and the import of `CONST_GRAFANA_DASHBOARD_GRID_WIDTH` that only it uses. Keep the constant in `src/devops_cli/config/constants.py`, which `src/devops_cli/grafana/builders.py` and `src/devops_cli/grafana/linter.py` use
- [ ] 4.3 Run the `git grep` command of task 4.1 (it prints nothing), then `uv run devops ci test tests/grafana` (it passes)
- [ ] 4.4 Run `git grep -n -w -e thinking_detected -e _get_ollama_semaphore -e unique_thinking -e _validation_error_key -e grid_width -- src tests docs` (it prints nothing), then `uv run devops ci` (exit code 0, and the coverage is at or above `fail_under` in `pyproject.toml`)
