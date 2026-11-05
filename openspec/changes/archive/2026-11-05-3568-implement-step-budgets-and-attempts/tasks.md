# Tasks

## 1. Add the budgets, the named stops and the attempt events

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_output_cap.py`, `src/devops_cli/roadmap/implement_trace.py`. Changes: `src/devops_cli/roadmap/implement_limits.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_trace.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/exceptions/ai_pydantic.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_limits.py`, `tests/roadmap/test_roadmap_implement_step_attempts.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_implement_limits.py`, add the tests of the four settings and of the stops: a step that spends the token budget or the time limit of the step or of the item makes no further request and names the setting; a repair turn makes no request after the budget; a step within every budget is not stopped
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_limits.py`
- [x] 1.2 In `tests/roadmap/test_roadmap_implement_step_attempts.py`, add the tests of the attempts: a failing check that passes on the second attempt shows both attempts; a failure that stays names `roadmap.implement.repair_rounds`; a group that changes no file is one attempt and gets no round; an attempt event is masked and printed by `explain --trace`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_attempts.py`
- [x] 1.3 Add `StepBudget` and `limit_hooks` in `src/devops_cli/roadmap/implement_limits.py`, the four settings, the class `limit_reached`, `LimitReached`, the `attempt` event, and the use of them in `run_step`, `run_fix_step` and the item run
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_limits.py tests/roadmap/test_roadmap_implement_step_attempts.py tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. Tell the reader

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `docs/ERRORS.md`.

- [x] 2.1 In `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`, describe the budgets, the class `limit_reached`, the line about the repair rounds and the attempt events, and regenerate the documents with `devops docs generate --sync-readme`
  - Verification: `uv run devops docs check`

## Workflow follow-up

- Strategy of each round (more context, a smaller group, a stronger tier) and the name of `roadmap.implement.ladder` in the stop of a one-tier ladder: #3569.
- The guard against a repeated failed tool call: #3570.
- The smaller edit for a `parser` failure: #3571.
- The reset of a moved HEAD: #3575.
- A group that changes no file returns for a smaller replacement: #3576.
- The repair of a failed verification command: #3577.
