# Tasks

## 1. The turn for a failed static check

- [x] Write failing tests in `tests/test_roadmap_implement_step_repair.py` and update `tests/test_roadmap_implement_step.py`: a step whose `ruff check` fails on an unused import ends done after the extra turn removes it; a step that still fails after the turn stops with the failure of the checks after the turn and the model gets no third turn; the turn gets the failure text, and lists the unticked tasks when there are any; a turn that changes a file the step did not change stops the step; a step with a static failure and an unticked task gets one extra turn; a failed verification command runs no turn; a static failure after the tick turn runs no second turn; a fix step gets the turn; the two turns share one budget.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_repair.py tests/test_roadmap_implement_step.py`
- [x] Change `src/devops_cli/roadmap/implement_step.py` and `src/devops_cli/lang/en/messages.py`: report which kind of check failed, extract one helper for the extra turn from `_tick_turn`, let `_foreign_change` take the paths a turn may change, and run the repair turn for a failed static check.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step_repair.py tests/test_roadmap_implement_step.py tests/test_roadmap_implement_step_ticks.py`

## 2. The instructions

- [x] Word the instructions of the step in `src/devops_cli/ai/tasks/roadmap_implement_step.md`: a failed static check gets one turn with the text of the failure, and a check that fails after that turn stops the step.
  - Verification: `uv run devops ci test tests/test_ai_task_implement.py tests/test_roadmap_implement_step.py`

## 3. The documentation

- [x] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2795-static-failure-repair-turn`
