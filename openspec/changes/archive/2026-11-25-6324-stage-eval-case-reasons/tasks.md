# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for `_ended` classification/masking and per-case text, JSON, and stored report output in `tests/roadmap/stage/test_roadmap_stage_eval_run.py` and `tests/roadmap/stage/test_roadmap_stage_eval_command.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_run.py tests/roadmap/stage/test_roadmap_stage_eval_command.py`
- [x] 1.2 Implement failure classification in `src/devops_cli/roadmap/stage/stage_eval_run.py`, attach `case_runs` to `StageScore` in `src/devops_cli/roadmap/stage/stage_eval_score.py`, and render masked `case_runs` in `src/devops_cli/roadmap/stage/stage_eval_render.py` and `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_run.py tests/roadmap/stage/test_roadmap_stage_eval_command.py`

## 2. Documents

- [x] 2.1 Update `docs/ROADMAP_WORKFLOW.md` if needed for per-case report entries and verify docs and OpenSpec checks
  - Verification: `$ uv run devops ci docs`
