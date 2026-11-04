# Tasks

## 1. Record a failed item and hold it for the retry delay

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/explain.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_retry.py`, `tests/roadmap/test_roadmap_stage_apply.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_retry.py` and `tests/roadmap/test_roadmap_stage_apply.py`, write the failing tests: a failure is recorded with its class and time; the selection leaves out an item inside the delay and takes it after; `--item` overrules the delay; a bad time holds nothing; `explain` reports a held item; a staged item clears the record; a stop records the failures before it and ends with the stop. Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_retry.py tests/roadmap/test_roadmap_stage_apply.py`
- [x] 1.2 Add `StageRecordKey.FAILED_AT` and `FAILED_ERROR`, the setting `roadmap.stage.retry_hours`, `_Judge._failed_lately`, `_record_failures` in `apply_stage`, the `item` field of `StageFailure`, and the clear of both keys in `_stage_one` and `_stop_on_budget`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_retry.py tests/roadmap/test_roadmap_stage_apply.py`

## 2. Fail the row only when no item was handled

Reads: `src/devops_cli/roadmap/run.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_stage_job.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_job.py`, write the failing tests that run three rounds of the real row with the ledger: one item fails while another stages (no suspension), every item fails (suspension), and an error outside any item (suspension). Change the test that expected a failed round after a staged item. Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_job.py`
- [x] 2.2 Add `raise_for_failed_round` and call it in `_run_stage_adapter`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_job.py tests/roadmap/test_roadmap_stage_retry.py`

## 3. Keep the causes of the ledger across a restart

Reads: `src/devops_cli/roadmap/run.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run.py`.

- [x] 3.1 In `tests/roadmap/test_roadmap_run.py`, write the failing tests: the record holds the causes and a new ledger loads them; a record of four fields loads with causes `unknown`. Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py`
- [x] 3.2 Write and read the causes in `FailureLedger`, and change its record type to accept both formats. Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py`

## 4. Count a round that a stop ends as stopped

Reads: `src/devops_cli/server/service.py`, `src/devops_cli/exceptions/roadmap.py`. Changes: `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/lang/en/messages.py`, `tests/server/test_server_service.py`.

- [x] 4.1 In `tests/server/test_server_service.py`, write the failing test: a scoped update and a round that a stop ends count as `stopped`, add no `error` count, and log no error line. Verification: `uv run devops ci test tests/server/test_server_service.py`
- [x] 4.2 Move `ended_by_stop` to `devops_cli.exceptions`, update its importers, and add `RepoWorker._end_in_stop` and use it in both execute methods. Verification: `uv run devops ci test tests/server/test_server_service.py tests/roadmap/test_roadmap_refine.py`

## 5. Documents

Changes: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`, and the generated `docs/CONFIGURATION.md`.

- [x] 5.1 Describe the failure record, the delay, the rule of the row and the `stopped` result in the documents, and regenerate the documentation with `uv run devops docs generate --sync-readme`. Verification: `uv run devops ci docs`
- [x] 5.2 Verify the whole change. Verification: `uv run devops ci`
