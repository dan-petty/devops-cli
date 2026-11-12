# Tasks

## 1. The returns of a refused stage reply are a setting (behavior)

- [x] 1.1 Write failing tests: a refused revision gets 3 returns by default, `roadmap.stage.gate_returns` sets the returns, and the setting has its variable.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/security/test_config_declarations.py`
- [x] 1.2 Add `roadmap.stage.gate_returns` (`DEFAULT_ROADMAP_STAGE_GATE_RETURNS`, 3), read it in the planner of `src/devops_cli/roadmap/stage/stage.py`, delete `CONST_ROADMAP_STAGE_GATE_RETURNS`, and update the tests that pinned one return.
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/test_roadmap_limit_classes.py`

## 2. A refused plan waits 1 hour (behavior)

- [x] 2.1 Write failing tests: `RETRY_AFTER` gives `plan_defect` 1 hour, and the stage job, refine and explain follow it.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/stage/test_roadmap_stage_retry_after.py tests/roadmap/refine/test_roadmap_refine_failure_class.py`
- [x] 2.2 Set the wait of `plan_defect` in `src/devops_cli/roadmap/failure.py` to 1 hour.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/stage/test_roadmap_stage_retry_after.py`

## 3. The failed rounds before a suspension are a setting (behavior)

- [x] 3.1 Write failing tests: a row runs 6 failed rounds by default, and `service.max_failed_rounds` sets the limit of the ledger.
  - Verification: `$ uv run devops ci test tests/github/test_service_limits.py`
- [x] 3.2 Add `service.max_failed_rounds` (`DEFAULT_SERVICE_MAX_FAILED_ROUNDS`, 6) and read it in `FailureLedger` of `src/devops_cli/roadmap/run.py`.
  - Verification: `$ uv run devops ci test tests/github/test_service_limits.py tests/roadmap/test_roadmap_run_failure_ledger.py tests/roadmap/test_roadmap_ledger_retry_after.py`

## 4. Documents

- [x] 4.1 Regenerate the settings documents, and state the new returns, wait and row limit in `docs/roadmap/stage.md`, `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md` and `k8s/README.md`.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
