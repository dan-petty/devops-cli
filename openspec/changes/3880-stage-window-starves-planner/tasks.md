# Tasks

## 1. Fail the plan run when the window starves it

Kind: behavior. Reads: `src/devops_cli/roadmap/refine_investigation.py`, `k8s/devops/configmap.example.yaml`. Changes: `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `k8s/devops/configmap.example.yaml`, `tests/roadmap/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_stage_window.py`, `tests/roadmap/test_roadmap_stage_apply.py`.

- [x] 1.1 Write the failing tests: a plan run whose tools the window ends before the least calls raises `RoadmapStageError` that names the window and the two settings; a run with enough calls returns its plan; a review run does not raise; the job records the window for the item; the window of the example ConfigMap is not below the least window. On the base the tests fail with no error from the run and with the window 65536.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_stage_window.py`
- [x] 1.2 Add `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` and the message `stage_window_starved`. Raise the error in `ToolboxClient.chat_structured` for a plan run. Set `ai.tasks.analysis.context_window` to 256000 in the example ConfigMap, with the comment.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_stage_window.py tests/k8s/test_k8s_configmap.py`
- [x] 1.3 Delete the stage-comment branch for a run that offered no tool, its message and its test.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_apply.py`

## 2. Fix the page of the stage job

Kind: documents. Changes: `docs/roadmap/stage.md`.

- [x] 2.1 State the window of the Service, and what the model does when the window ends the tools too soon.
  - Verification: `uv run devops ci docs`
- [x] 2.2 Check the specs and the change.
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- Pending a person: the window of the task `verification` in the example ConfigMap (criterion 1 of the issue) waits for the pull request of #3874, which edits the same lines.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
