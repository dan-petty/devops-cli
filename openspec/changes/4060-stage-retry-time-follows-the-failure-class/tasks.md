# Tasks

## 1. Wait for the time of the failure class

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_retry_after.py`, `tests/roadmap/test_roadmap_failure.py`. Changes: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_retry_after.py`, `tests/roadmap/stage/test_roadmap_stage_retry.py`, `tests/roadmap/test_roadmap_failure.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_retry_after.py` and `tests/roadmap/test_roadmap_failure.py`, write the tests of the criteria: a provider error waits 1 hour and a refused plan waits 6 hours, an item-changed error waits 0, a record with no class or an unknown class waits as `ci_infra`, the selection stores no retry time, `explain` gives the time of the class, and the keys of `RETRY_AFTER` are exactly the classes of `CLASS_BY_EXCEPTION`. Change `tests/roadmap/stage/test_roadmap_stage_retry.py` to the wait of `ci_infra`. Confirm that the tests fail on `origin/main`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_retry_after.py`
- [x] 1.2 Add `RETRY_AFTER` to `src/devops_cli/roadmap/failure.py`. Change `_Judge._failed_lately` to read `StageRecordKey.FAILED_CLASS` and wait until `failed_at + RETRY_AFTER[class]`, with `ci_infra` for a missing or unknown class. Remove the `retry` argument of `_Judge` and its read of the settings in `select_stageable`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_retry_after.py`
- [x] 1.3 Run the tests of the stage job and the explain command
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## 2. Remove the setting retry_hours

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 2.1 In `tests/roadmap/stage/test_roadmap_stage_settings.py`, write the test that a config file with `roadmap.stage.retry_hours` loads and that the stage settings hold no such field. Remove the table entry of `DEFAULT_ROADMAP_STAGE_RETRY_HOURS` in `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_settings.py`
- [x] 2.2 Remove the field `retry_hours` of `RoadmapStageConfig` and its import in `src/devops_cli/config/settings.py`, and `DEFAULT_ROADMAP_STAGE_RETRY_HOURS` in `src/devops_cli/config/defaults.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_limit_classes.py`

## 3. Fix the documents and the comments

Kind: documents. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `k8s/README.md`, `openspec/specs/roadmap-stage/spec.md`, `openspec/specs/roadmap-explain/spec.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/CONFIGURATION.md`, `k8s/README.md`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/run.py`.

- [x] 3.1 Replace the retry hours with the wait of the failure class in `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, item 15 of the Roadmap service list in `k8s/README.md`, and the comments of `src/devops_cli/roadmap/stage/stage.py` and `src/devops_cli/roadmap/run.py`. Regenerate `docs/CONFIGURATION.md` with `uv run devops docs generate --sync-readme`
  - Verification: `$ ! grep -rIiq 'retry_hours' src docs k8s README.md && uv run devops docs generate --check`
- [x] 3.2 Check the change and the specs
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: A provider error waits 1 hour and a refused plan waits 6 hours. An item-changed error waits 0. A record with no class waits as `ci_infra`.
- Group 1: The keys of `RETRY_AFTER` are exactly the classes of `CLASS_BY_EXCEPTION`.
- Group 2: A config file that names `roadmap.stage.retry_hours` loads, and the stage settings hold no such field.
- Group 3: No file in `src`, `docs`, `k8s` or `README.md` names `retry_hours`, and the generated documents are up to date.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
