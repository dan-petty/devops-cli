# Proposal

## Why

A run of the stage eval needs its own context window, and the only way to set it is to edit the live config (#4225). The issue #3566 names the variable `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW`, but the variable does not exist: with it set to 131072, `ai.for_task("stage").context_window` is still 262144, and no error tells the person. The task `verification` has no variable at all. The fields `context_window` and `max_tokens` exist on every task, so only the variables are missing.

## What Changes

- Add the variables `DEVOPS_CLI_AI_TASK_<TASK>_CONTEXT_WINDOW` and `DEVOPS_CLI_AI_TASK_<TASK>_MAX_TOKENS` for the tasks `analysis`, `stage` and `verification`. They set `ai.tasks.<task>.context_window` and `ai.tasks.<task>.max_tokens`.
- Add a second tuple of task variable fields to `src/devops_cli/config/settings.py`, and give `analysis` and `stage` the fields of both tuples. Give `verification` the new fields only, as its first `Variable` marker.
- A variable is optional. A deployed config that sets none keeps its values.
- Regenerate `docs/ENV_VARS.md` with `uv run devops docs generate`, and tell the new variables in `docs/ROADMAP_WORKFLOW.md`.
- Add the six names to the expected set of `tests/security/test_config_declarations.py`.
- Tests: `tests/config/test_ai_task_settings_paths.py` sets each variable and reads `for_task(task)`.
- The change adds a variable, which a person observes, so it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-task-models`: the variables of the stage task now include the window and the reply limit, and a new requirement covers the three tasks.

## Impact

- Code: `src/devops_cli/config/settings.py`
- Documents: `docs/ENV_VARS.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/config/test_ai_task_settings_paths.py`, `tests/security/test_config_declarations.py`
- Deployment: none. The change adds a variable and removes no key, so the live ConfigMap needs no change and no rollout order applies. The `Settings` models ignore unknown keys (`extra="ignore"`), while `AITasksConfig` and `AITaskOverride` use `extra="forbid"`. A new variable adds no key to the file, so neither rule matters here.

## Feasibility

- Checked on 2026-11-09 on origin/main `7411967a`. With `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW=131072`, `load_settings().ai.for_task('stage').context_window` returned `262144`. The variable has no effect and raises no error.
- `src/devops_cli/config/settings.py` line 618 holds `_TASK_VARIABLES = ("provider", "model", "reasoning_effort", "ollama_urls")`. The tasks `chat`, `metadata`, `analysis` and `stage` use it as `Variable(fields=_TASK_VARIABLES)`. The task `embedding` adds `timeout`. The task `verification` has no marker.
- `AITaskOverride` already has `context_window` and `max_tokens` (lines 571 to 573), and `AIConfig._with_task` copies them, so a variable only has to name the fields. The generator in `src/devops_cli/config/env.py` reads `Variable.fields` and builds the name and the doc row.
- Probe after the tests: the new tests fail on origin/main for this reason alone. `tests/config/test_ai_task_settings_paths.py` reads 32768 (window) and `None` (max tokens) where the variable says another value, and `tests/security/test_config_declarations.py` lacks the six names in the variables read.
- The stage task takes unset fields from the analysis task (`_TASK_PARENTS`), so a window variable of `analysis` also moves `stage` until `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` is set. This is the existing rule, and the new test pins that the stage variable wins.
- No open or merged pull request touches `_TASK_VARIABLES`. The builds of #4220, the window estimate and #3665 touch other files.
- The set claim: the issue names three tasks (`stage`, `analysis`, `verification`). The tasks `chat`, `metadata`, `embedding`, `compose`, `implement` and `triage` are not in the set of the issue, and no window variable is asked for them.

## Existing Tool Considered

The `Variable` marker and the generator of `src/devops_cli/config/env.py` already declare a variable, so no new code path and no library is needed. The change adds one tuple and one marker. Cost: about 2,000 tokens to build, none to keep (the generator keeps the doc), and about 30 minutes. The change deletes no internal code.
