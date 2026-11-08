# Tasks

## 1. Name the class of an exception and the step

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/exceptions/roadmap.py`, `tests/roadmap/test_roadmap_failure.py`. Changes: `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_failure.py`, write the tests `class_by_exception` and `step_name`: each mapped exception gives its class, a specific type comes before its parent, a subclass with no entry gives the class of its parent, the last entry is `DevOpsCLIError`, and the values of `StepName` are unique one-word strings
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`
- [ ] 1.2 Add `StepName`, `CLASS_BY_EXCEPTION` and `failure_class_of` to `src/devops_cli/roadmap/failure.py`, and export them. Check that the new imports make no import cycle
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`

## 2. Record the class and the step of a stage failure

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/stage/test_roadmap_stage_failure_class.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/stage/test_roadmap_stage_failure_class.py`, `tests/roadmap/stage/test_roadmap_stage_retry.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`.

- [ ] 2.1 In `tests/roadmap/stage/test_roadmap_stage_failure_class.py`, write the tests of the criteria: a provider error records `provider` and `plan`, a refused plan records `plan_defect`, a failed write records `apply`, an item-changed error records `head_moved`, a staged item and an item stopped on the budget clear the four keys, and a failure costs no extra request. Pass the two new fields in the tests that build a `StageFailure` by hand. Confirm that the tests fail on `origin/main`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 2.2 Add `FAILED_STEP = "stage.failed_step"` and `FAILED_CLASS = "stage.failed_class"` to `StageRecordKey`. Add the required keyword-only fields `failure_class` and `step` to `StageFailure`. Set them in `_failure_of` (step `plan`) and `_write_failure` (step `apply`) with `failure_class_of`. Write both keys in `_record_failures`, and clear both where `stage.failed_at` is cleared
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_failure_class.py`
- [ ] 2.3 Run the tests of the stage job and the key-walk test of the example ConfigMap
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## 3. Fix the documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage.py`.

- [ ] 3.1 Add `stage.failed_step` and `stage.failed_class` to the table of keys in `docs/ROADMAP_WORKFLOW.md`, update the failure paragraph in `docs/roadmap/stage.md`, and update the docstrings of `StageRecordKey` and of the module `stage.py`
  - Verification: `$ grep -q 'stage.failed_class' docs/ROADMAP_WORKFLOW.md && uv run devops docs generate --check`
- [ ] 3.2 Check the change and the specs
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: Each mapped exception gives its class by `isinstance`, and a subclass with no entry gives the class of its parent.
- Group 1: The values of `StepName` are unique one-word strings.
- Group 2: A provider error records the class `provider` and the step `plan`. A refused plan records `plan_defect`. A failed write records the step `apply`. An item-changed error records `head_moved`.
- Group 2: A staged item clears the keys.
- Group 3: The workflow document names the new keys, and the generated documents are up to date.

## Workflow follow-up

- The retry time by class is the issue #4060.
- The output of `explain` and `inbox` is the issue #3648.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
