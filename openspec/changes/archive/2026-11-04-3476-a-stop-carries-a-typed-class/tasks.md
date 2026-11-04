# Tasks

## 1. Add the five classes and read the failure, not the claim

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`.

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_failure.py` for "The failure classes", "A pure classifier", "Real excerpts map to their class" and "One default action for each class": the 17 classes, the table of actions, the field `log`, no field for the last message of the agent, the words `already implemented` in a stop text for another cause, and a fixture of synthetic stop texts that follow the patterns of #3476
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py` fails on the base
- [x] 1.2 Add the classes, their rows in `ACTION_BY_CLASS` and `evidence.log`, and remove `agent` from `FailureEvidence`, the premise match on the agent text and the two plan patterns that the typed stops replace
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py`

## 2. Type the stops of the step and the job

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_failure_class.py` (new), `tests/roadmap/test_roadmap_implement_job_scoped.py`, `tests/roadmap/test_roadmap_implement_step_output_cap.py`, `tests/roadmap/test_roadmap_implement_step_tests_kept.py`.

- [x] 2.1 Write failing tests for "A stop site passes a typed class", "A stop names the failed check and the end of its log" and "The comment puts the failed check first and labels the claim": the class of each step stop, the tier decision, the fix-step stop that names its check with the log masked, the scoped-check stop, the record keys, the removal on retry and the order of the comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_failure_class.py tests/roadmap/test_roadmap_implement_job_scoped.py tests/roadmap/test_roadmap_implement_step_output_cap.py tests/roadmap/test_roadmap_implement_step_tests_kept.py` fails on the base
- [x] 2.2 Pass the class from `_exit_failure`, `_unticked_failure` and `_run_turn` through `StepOutcome.failure_class` to `_stopped_by`, read it in `_moves_tier`, pass the check and the log from `_fix` and the scoped-check stop, add `implement.check` and `implement.check_log`, and change the stop comment
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_failure_class.py tests/roadmap/test_roadmap_implement_job_scoped.py tests/roadmap/test_roadmap_implement_step_output_cap.py tests/roadmap/test_roadmap_implement_step_tests_kept.py`

## 3. Read the item again in the report and guard the metric labels

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_submit.py`, `k8s/README.md`. Changes: `src/devops_cli/roadmap/implement_submit.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/prometheus/test_implement_failure_labels.py` (new).

- [x] 3.1 Write failing tests for "The report reads the item again" and "The metric labels are classes of the taxonomy": a runner that writes its stop while the report reads the log, and the scan of the files of `k8s/`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/prometheus/test_implement_failure_labels.py` fails on the base
- [x] 3.2 Read the item again in `_report` after the log read
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/prometheus/test_implement_failure_labels.py`

## 4. Document the classes and the record keys

Kind: documents. Reads: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`.

- [x] 4.1 Add the five classes with their actions to the table of `docs/ROADMAP_WORKFLOW.md`, state that the classifier reads no claim of the agent, add the keys `implement.check` and `implement.check_log`, and name the new class values in the `/metrics` list of `k8s/README.md`
  - Verification: `uv run devops ci --check --only docs`

## 5. Archive the change

Kind: other. Changes: `openspec/changes/3476-a-stop-carries-a-typed-class`, `openspec/specs/roadmap-failure-taxonomy/spec.md`, `openspec/specs/roadmap-implement-job/spec.md`.

- [x] 5.1 Archive the change after every task is ticked
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- Recovery from a no-op group belongs to #3460.
- The clear rule for a stop that a new runner image can fix belongs to #3481.
- A case in the fault set for each new class belongs to #3075, which has no fault set yet.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
