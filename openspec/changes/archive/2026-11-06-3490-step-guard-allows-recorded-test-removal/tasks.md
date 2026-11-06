# Tasks

## 1. Read the weakened checks of a plan

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_read_weakened.py` (new), `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 Write tests that read a section into `weakened_checks`, refuse a line in another form, list the `path::name` of each entry, and read the record at a commit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read_weakened.py` fails on the base
- [x] 1.2 Add `WeakenedCheck`, the field, `weakened_checks`, `recorded_tests` and `merged_recorded_tests`, and let the test of the reply keys read the schema
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read_weakened.py tests/roadmap/test_roadmap_stage_prompt_rules.py tests/roadmap/test_roadmap_plan_read.py` passes

## 2. Allow a removal that the merged plan records

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_test_names.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_test_names.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_step_tests_kept.py`, `tests/roadmap/test_roadmap_implement_job_recorded_tests.py` (new), `tests/roadmap/test_roadmap_implement_prompt.py`.

- [x] 2.1 Write tests: a recorded removal, rename and move pass the step and its `wip:` commit, an unrecorded removal stops it, the job reads the record from the default branch only, and the prompt allows a recorded removal
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_tests_kept.py tests/roadmap/test_roadmap_implement_job_recorded_tests.py tests/roadmap/test_roadmap_implement_prompt.py` fails on the base
- [x] 2.2 Give `run_step` and `run_fix_step` the argument `recorded_tests`, filter the lost tests in `_tests_failure`, read the record in the job, and change the prompt and the reason of the stop
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_tests_kept.py tests/roadmap/test_roadmap_implement_job_recorded_tests.py tests/roadmap/test_roadmap_implement_prompt.py` passes

## 3. Let a lost test wait for a person

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stop_clear.py`. Changes: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stop_clear.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_stop_clear.py`.

- [x] 3.1 Change the row of the table test, and add a test that a new image does not clear a stop of the class `tests_lost`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_stop_clear.py` fails on the base
- [x] 3.2 Set the action of `FailureClass.TESTS_LOST` to `wait`, and name a lost test in the docstring of `stop_clear.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_stop_clear.py` passes

## 4. Read the record in the eval property

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_eval.py`, `src/devops_cli/roadmap/implement_eval_run.py`, `src/devops_cli/roadmap/implement_eval_properties.py`. Changes: `src/devops_cli/roadmap/implement_eval.py`, `src/devops_cli/roadmap/implement_eval_run.py`, `src/devops_cli/roadmap/implement_eval_properties.py`, `tests/support/roadmap_eval.py`, `tests/roadmap/test_roadmap_implement_eval_properties.py`, `tests/roadmap/test_roadmap_implement_eval_run.py`, `tests/roadmap/test_roadmap_implement_eval_fixtures.py`.

- [x] 4.1 Write tests: `tests_kept` passes a removal that the section of the fixture names, also a test of a class that the section names as `path::Class.name`, and refuses one that it does not name, and the eval run gives the list to the step
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_properties.py tests/roadmap/test_roadmap_implement_eval_run.py` fails on the base
- [x] 4.2 Add the record to `allow_lost_tests` in `load_case`, pass the list in `run_case`, and let `tests_kept` read an entry `path::Class.name` as the name after the last dot, because a hunk shows no class
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_eval_properties.py tests/roadmap/test_roadmap_implement_eval_run.py tests/roadmap/test_roadmap_implement_eval_fixtures.py` passes

## 5. Record the removals of the open plans

Reads: `openspec/changes/2519-the-claim-table-of-the-local/tasks.md`, `openspec/changes/2592-devops-ai-gateway-tune-recommends-weights/tasks.md`, `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md`, `openspec/changes/2636-a-result-that-no-lookup-marked/tasks.md`, `tests/invariants/test_change_folders.py`. Changes: `openspec/changes/2519-the-claim-table-of-the-local/proposal.md`, `openspec/changes/2592-devops-ai-gateway-tune-recommends-weights/proposal.md`, `openspec/changes/2610-devops-k8s-image-pins-resolves-with/proposal.md`, `openspec/changes/2636-a-result-that-no-lookup-marked/proposal.md`, `openspec/changes/3320-a-plan-that-deletes-a-guard/proposal.md`, `openspec/changes/3320-a-plan-that-deletes-a-guard/tasks.md`, `openspec/changes/3320-a-plan-that-deletes-a-guard/design.md`, `openspec/changes/3328-the-stage-probe-checks-prompt-reply/proposal.md`, `openspec/changes/3328-the-stage-probe-checks-prompt-reply/design.md`, `tests/invariants/test_change_folders.py`.

The plans of #3320 and #3328 quote the assertion `StageProposal.model_fields` of the test of the reply keys, which this change turns into the properties of the schema. Task 5.1 changes those quotes.

- [x] 5.1 Add a `## Weakened checks` section to each of the four plans, with an entry for each test that a task of the plan removes, renames or moves, and name a test of a class as `path::Class.test_x`, as the guard reads it. Change the plan of #3320 to use the reader, the model and the form of this change, and the quotes of the old assertion in the plans of #3320 and #3328
  - Verification: `uv run devops openspec check` passes
- [x] 5.2 Add a check to the invariants over the change folders: an entry that names a test of a class with no class, or with another class, is a problem, and so is a section that the reader refuses
  - Verification: `uv run devops ci test tests/invariants/test_change_folders.py` fails with the entries of the base (`tests/ai/test_ai_gateway_tune.py::test_recommend_weights_with_overrides`) and passes with the qualified names

## 6. Say what the guard allows

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`.

- [x] 6.1 Change the row of `tests_lost`, the row of `tests_kept` and the text of the guard in `docs/ROADMAP_WORKFLOW.md`, and the exit check of the tests in `docs/roadmap/implement.md`, then run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 2: A test: a removal that `weakened_checks` names passes the guard.
- Group 2: A test: a removal that `weakened_checks` does not name stops the step.
- Group 2: A test: a rename or a move passes when the entry names the old test.
- Group 2: A test on `roadmap_implement_step.md`: the prompt allows a removal that the plan records.
- Group 3: A test: a stop for a lost test that the plan orders does not read `ci_infra` with `retry`.
- Group 4: A test: `TESTS_KEPT` passes a removal that the record names, through the same list as `allow_lost_tests`.
- Group 5: Each plan of #2519, #2592, #2610 and #2636 that is still under `openspec/changes` holds an entry. `git grep -l "Weakened checks" openspec/changes` lists each one.

## Workflow follow-up

- #3320 adds the reply key, the writer and the gate that fill this record.
- #3053 holds the repair turn of a test that a model loses by error.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
