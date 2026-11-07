# Tasks

## 1. Set the review window and fail a starved review run

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `k8s/devops/configmap.example.yaml`. Changes: `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`, `k8s/devops/configmap.example.yaml`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`.

- [x] 1.1 Write the failing tests: a review run whose tools the window ends before the least calls raises `RoadmapStageError` that names the window and `ai.tasks.verification.context_window`; a review run with enough calls returns its findings; the window of the task `verification` in the example ConfigMap is not below the least window of a review run, and equals the window of `analysis`. On the base the tests fail with no error from the run and with no window set.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py`
- [x] 1.2 Add the message `stage_verify_window_starved`. Check the window for a review run as for a plan run. Set `ai.tasks.verification.context_window` to 256000 in the example ConfigMap, with the comment.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py`

## 2. Fix the page of the stage job

Kind: documents. Changes: `docs/roadmap/stage.md`.

- [x] 2.1 State the window of the task `verification` and the failure of a starved review run.
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Check the specs and the change.
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
