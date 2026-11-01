# Proposal

## Why

Issue #2175: five definitions in `src/` have no caller. Issue #1910 does not list them. Nothing registers them with a decorator, and none overrides a library method. They are dead code, and a reader must still read and keep them. The change deletes them.

The deletion keeps every behavior that a consumer can see. No `devops` command, option or message, no manifest and no service behavior changes. The change therefore has no spec delta and sets `skip_specs: true`.

The change fits one pull request.

## What Changes

- Delete `StreamingTokenProcessor.thinking_detected` from `src/devops_cli/ai/client/streaming.py`.
- Delete `ThinkingStreamProcessor.unique_thinking` from `src/devops_cli/ai/thinking_stream.py`.
- Delete `LLMClient._get_ollama_semaphore` from `src/devops_cli/ai/client/unified.py`, and the `import threading` that only it uses.
- Delete the code that only `_get_ollama_semaphore` used in `src/devops_cli/ai/client/network.py`: `get_ollama_semaphore`, `ollama_semaphores` and `ollama_sem_lock`, and their reset in `reset_ollama_slots`.
- Delete `_validation_error_key` from `src/devops_cli/config/settings.py`.
- Delete `Dashboard.grid_width` from `src/devops_cli/grafana/schema.py`, and the import of `CONST_GRAFANA_DASHBOARD_GRID_WIDTH` that only it uses.
- No test calls a deleted name, so the change deletes no test and adds none. Each group names the command that verifies it.

## Acceptance

| Criterion of the issue | Group |
| :--- | :--- |
| The five definitions are deleted | 1 (`thinking_detected`, `unique_thinking`), 2 (`_get_ollama_semaphore`), 3 (`_validation_error_key`), 4 (`grid_width`) |
| `git grep -n -w <name>` prints nothing in `src/`, `tests/` and `docs/` for each name | The first task of each group |
| A test that only calls a deleted name goes with it, and the pull request names it | No such test exists (see Feasibility), so no test goes. The pull request says so |
| `uv run devops ci` passes, and the coverage stays at or above `fail_under` (85 in `pyproject.toml`) | The last task of group 4 |

## Feasibility

All commands ran on `origin/main` at 1c20865a on 2026-11-01.

- Each name appears only at its definition. `git grep -n -w <name> -- . ':!openspec'` printed one line for each of the five names:
  - `src/devops_cli/ai/client/streaming.py:161:    def thinking_detected(self) -> bool:`
  - `src/devops_cli/ai/client/unified.py:164:    def _get_ollama_semaphore(cls, url: str, max_parallel: int) -> threading.Semaphore:`
  - `src/devops_cli/ai/thinking_stream.py:339:    def unique_thinking(self) -> str:`
  - `src/devops_cli/config/settings.py:187:def _validation_error_key(exc: ValidationError, prefix: tuple[str, ...] = ()) -> str:`
  - `src/devops_cli/grafana/schema.py:145:    def grid_width(self) -> int:`
- The line numbers of the issue are old for three names (161, 164 and 187, not 164, 215 and 219). The definitions are still on `origin/main`, and `git log -S<name> -- src tests` lists no commit that moved or removed any of them (the newest commit for `_validation_error_key` is #2124, the newest for `thinking_detected` is #2074). No newer plan or issue reuses them.
- The search covered the whole tree except `openspec/`, so it also covered `docs/`, the knowledge base, `k8s/`, `.github/` and every `*.md`, `*.yaml` and `*.toml`. No string, registry or entry point names any of the five.
- No test calls a deleted name. `git grep -n -w <name> -- tests` printed nothing for all five. Criterion 3 of the issue therefore needs no deletion of a test.
- No base spec under `openspec/specs/` names any of the five (`grep -rn` over `openspec/specs` printed nothing). No other active change folder names them.
- Exclusive users that go with the definitions:
  - `import threading` in `src/devops_cli/ai/client/unified.py`: `git grep -n -w threading -- src/devops_cli/ai/client/unified.py` printed line 6 (the import) and line 164 (the deleted method). Nothing else uses it.
  - `network.get_ollama_semaphore` (`src/devops_cli/ai/client/network.py:316`) has one caller, `src/devops_cli/ai/client/unified.py:165`, inside the deleted method. The module state `ollama_semaphores` (line 46) and `ollama_sem_lock` (line 47) are read only by that function and by `reset_ollama_slots` (lines 590 and 591). After the method goes, all three are dead, so they go with it. The string `"_ollama_semaphores"` in `tests/ai/client/test_ai_client_security.py:208` is another name (it starts with an underscore) and stays.
  - `CONST_GRAFANA_DASHBOARD_GRID_WIDTH` in `src/devops_cli/grafana/schema.py`: the import (line 19) and `grid_width` (line 147) are its only uses in that file. The constant stays in `src/devops_cli/config/constants.py:2157` because `src/devops_cli/grafana/builders.py` and `src/devops_cli/grafana/linter.py` use it.
  - `unique_lines` in `src/devops_cli/ai/thinking_stream.py` stays: line 390 also uses it.
  - `ValidationError` in `src/devops_cli/config/settings.py` stays: `_format_validation_error` (line 196) and the `except ValidationError` clauses (for example lines 1375 and 1399) use it.
  - `has_reasoning` in `src/devops_cli/ai/client/streaming.py` stays: `thinking_detected` only returned it, and line 202 also reads it.
- `pyproject.toml` has `fail_under = 85`. Deleting dead lines does not lower the covered share of the live lines.

## Existing Tool Considered

`git grep -w` proves that a name has no caller, and the plan uses it. No dead-code tool is added. Issue #1910 states that `vulture` is not a gate, because the trial needed 12 decorator patterns and 7 name patterns first. The `ruff` check of `devops ci lint` finds an unused import, so it checks that the groups leave none.

The internal code that the change deletes: `StreamingTokenProcessor.thinking_detected`, `ThinkingStreamProcessor.unique_thinking`, `LLMClient._get_ollama_semaphore`, `network.get_ollama_semaphore`, `network.ollama_semaphores`, `network.ollama_sem_lock`, `_validation_error_key` and `Dashboard.grid_width`.
