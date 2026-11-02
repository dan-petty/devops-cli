# Tasks

## 1. Refuse a verify command and a test path in the wrong form

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Creates: `src/devops_cli/roadmap/stage_form.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [x] 1.1 Add `tests/roadmap/test_roadmap_stage_form.py` with the cases that `uv run pytest` and a flat new test path get the problem text, that the accepted forms and the mirror and invariant paths get none, and that a plan with no source path refuses only a test directly under `tests/`, and verify that `uv run devops ci fail-to-pass --base origin/main` fails on the base
- [x] 1.2 Add `src/devops_cli/roadmap/stage_form.py` with `form_problems`, call it in `check_proposal` of `src/devops_cli/roadmap/stage_change.py`, and add the messages `stage_problem_verify` and `stage_problem_test_path` to `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes
- [x] 1.3 Change the `verify` of the sample plans in `tests/roadmap/test_roadmap_stage_plan.py` that name `uv run pytest` to `uv run devops ci test`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Give the prompt and the rules a mirrored example

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `openspec/config.yaml`, `docs/TESTING.md`, `tests/roadmap/test_roadmap_stage_form.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `openspec/config.yaml`, `docs/TESTING.md`.

- [x] 2.1 The test `test_every_example_test_path_of_the_prompt_and_the_config_is_mirrored` of `tests/roadmap/test_roadmap_stage_form.py` fails on the base because both examples are `tests/test_<feature>.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes after the edit
- [x] 2.2 Replace the example with `tests/roadmap/test_feature.py` in `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `openspec/config.yaml`, state the mirror rule and the `verify` form in both, and name `uv run devops openspec check` and `uv run devops k8s image-pins` in `docs/TESTING.md`, and verify that `uv run devops docs check` passes

## 3. Replay the recorded plans with a pytest verify command

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`. Changes: `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/2116-the-scanner-executor-tests-find-the/case.json`, `tests/fixtures/roadmap_eval/stage/2260-uv-test-pipeline-serve-mcp-and/case.json`, `tests/fixtures/roadmap_eval/stage/2369-the-startup-import-tests-start-56/case.json`, `tests/fixtures/roadmap_eval/stage/2462-devops-ai-cost-report-shows-a/case.json`.

- [x] 3.1 Add a test in `tests/roadmap/test_roadmap_stage_eval_gates.py` that the replay of the plans of #2975, #2977, #2985 and #2990 is refused by the `paths` gate for the verify-form defect, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [x] 3.2 Set the gate `paths` and the message ``A `verify` command starts with `uv run devops` `` on the pytest verify-form defect of those four cases, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
