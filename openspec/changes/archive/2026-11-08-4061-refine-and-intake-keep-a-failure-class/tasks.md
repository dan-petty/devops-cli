# Tasks

## 1. Name the steps and the refine keys

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/test_roadmap_failure.py`. Changes: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/test_roadmap_failure.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_failure.py`, change the test of `StepName` to the four steps `plan`, `apply`, `investigate` and `place`. Confirm that it fails on `origin/main`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`
- [x] 1.2 Add `INVESTIGATE` and `PLACE` to `StepName`, and `FAILED_AT`, `FAILED_STEP` and `FAILED_CLASS` to `RefineRecordKey`, with the values `refine.failed_at`, `refine.failed_step` and `refine.failed_class`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`

## 2. Refine records the class and waits

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_failure_class.py`, `tests/roadmap/refine/test_roadmap_refine_failure_record.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_failure_class.py`, `tests/roadmap/refine/test_roadmap_refine_failure_record.py`.

- [x] 2.1 In `tests/roadmap/refine/test_roadmap_refine_failure_class.py`, write the tests of the criteria: a timeout records the class, the step and the time and marks the item as at fault for nothing; the next round skips the item until the wait of its class passes; a success and a failed form check clear the keys; a record with no class, an unknown class or a bad time; `--item` overrules; a body edit ends the wait; `explain` gives the time; a placeholder failure records nothing. Change `test_roadmap_refine_failure_record.py` to the new behavior and remove the test that a timeout records nothing. Confirm that the new tests fail on `origin/main`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_failure_class.py`
- [x] 2.2 Add `failure_class` to `RefineFailure`. In `_record_failure`, write the three keys for each failure that is not a placeholder failure, in the one marks write of the failed body hash when the text caused the failure, and clear them on the second failure on the same body. Clear them in `_failure_marks` for a round whose model call worked. Make `has_writes` true for such a failure
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_failure_class.py tests/roadmap/refine/test_roadmap_refine_failure_record.py tests/roadmap/refine/test_roadmap_refine_placeholder.py`
- [x] 2.3 In `_Selection.consider`, leave the item out until `refine.failed_at` plus `retry_after(refine.failed_class)`, with the step `retry` and the time in the detail, and end the wait when the body hash differs from `refine.failed_body_hash`. Change the text `refine_left_waits["retry"]` so that it reads right for both causes
  - Verification: `$ uv run devops ci test tests/roadmap/refine`

## 3. Intake keeps the failure and waits

Kind: behavior. Reads: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/intake/test_roadmap_intake_failure_class.py`. Changes: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/intake/test_roadmap_intake_failure_class.py`.

- [x] 3.1 In `tests/roadmap/intake/test_roadmap_intake_failure_class.py`, write the tests of the criteria: `repeated_failure`, `old_record` and `no_item_mark`, and the tests of the count, the webhook update, a changed Item, a closed candidate and `plan_intake`. Confirm that they fail on `origin/main`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_failure_class.py`
- [x] 3.2 Add the model `Failed` and the field `IntakeRecord.failed`, `PlacementFailure.failure_class` and `IntakePlan.held`. Give `plan_intake` the parameters `failed` and `now`, and drop the held candidates before the queue. Add `IntakeRecord.settled`, and make `after` and `merged` keep the entries of the candidates they do not decide
  - Verification: `$ uv run devops ci test tests/roadmap/intake`
- [x] 3.3 In `run.py`, pass `failed` and `now` to `plan_intake` in `_run_intake_adapter` and `_intake_one`, and write `record.settled(...)` in `_apply_round` after `apply_intake` and before `raise_for_failed_placements`
  - Verification: `$ uv run devops ci test tests/roadmap/intake tests/roadmap/test_roadmap_run_scoped_update.py tests/roadmap/test_roadmap_run_due_table.py`

## 4. Fix the documents

Kind: documents. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/refine.md`, `docs/roadmap/intake.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/refine.md`, `docs/roadmap/intake.md`.

- [x] 4.1 In `docs/ROADMAP_WORKFLOW.md`, add the row of the keys `refine.failed_at`, `refine.failed_step` and `refine.failed_class`, and state that the Service keeps the intake failure in its record file. In `docs/roadmap/refine.md` (Failures) and `docs/roadmap/intake.md`, describe the wait of a failure class. Regenerate the documents if a message changed
  - Verification: `$ uv run devops docs generate --check`
- [x] 4.2 Check the change and the specs
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: `StepName` holds `plan`, `apply`, `investigate` and `place`.
- Group 2: A timeout in refine records class, step and time. The next round skips the item until the time passes. A success clears the keys.
- Group 3: The second round makes no triage call for a candidate with a recorded class. The count is in `IntakeRecord` only. A record file from before the change loads. The item record gets no mark for an intake failure.
- Group 4: The documents describe the keys, the record and the wait, and the generated documents are up to date.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
