# Tasks

## 1. The stage task and its fallback

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/stage.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `tests/config/test_stage_task_setting.py`.

- [x] 1.1 Add the test `tests/config/test_stage_task_setting.py` for the model, the fallback to `analysis` and the variable.
  - Verification: `uv run devops ci test tests/config/test_stage_task_setting.py`
- [x] 1.2 Add `stage` to `AITasksConfig` and the parent table to `AIConfig.for_task`.
- [x] 1.3 Make the stage job, the stage command and the Service round ask for the model and the window of the task `stage`. Change the tests of the command and the job to expect `stage`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_command.py tests/roadmap/test_roadmap_stage_job.py`

## 2. Tokens and spend in the eval report

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage_eval_render.py`. Changes: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage_eval_render.py`, `src/devops_cli/roadmap/stage_eval_usage.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`, `tests/roadmap/test_roadmap_stage_eval_usage.py`.

- [x] 2.1 Add tests for the `usage` field of the report (priced model, unpriced model), for the printed lines and for `RunUsage`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_command.py tests/roadmap/test_roadmap_stage_eval_usage.py`
- [x] 2.2 Add `RunUsage`, wrap the run in `observe_llm_calls`, and print and store the tokens and the spend. Make the eval use the task `stage`.

## 3. Documents

Kind: documents. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/ENV_VARS.md`, `README.md`.

- [x] 3.1 Add the test that reads the section, then define the acceptable stage score, the task `stage` and the baseline steps in `docs/ROADMAP_WORKFLOW.md`. Update the window text in `docs/roadmap/stage.md`.
  - Verification: `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py tests/invariants/test_roadmap_stage_measure_doc.py`
- [x] 3.2 Regenerate the generated documents.
  - Verification: `uv run devops ci docs`

## 4. Archive

Kind: documents.

- [x] 4.1 Archive the change with `uv run devops openspec archive 3207-score-stage-cloud-model`.

## Workflow follow-up

- Pending a person: set `ai.tasks.stage.model` in the deployed config after the baseline passes, and park #3066 and #3060 until then.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
