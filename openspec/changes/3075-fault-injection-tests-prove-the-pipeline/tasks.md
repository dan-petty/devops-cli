# Tasks

## 1. Add the stage and implement fault matrix

Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `tests/support/roadmap_implement.py`, `tests/support/model_script.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_failure.py`, `docs/TESTING.md`. Changes: `tests/roadmap/test_roadmap_faults.py` (new).

- [ ] 1.1 Add `tests/roadmap/test_roadmap_faults.py`. The module docstring says the suite runs offline on the edge fakes, that no wait is real, and states its measured duration. Define `FaultCase` with the case name, the `FailureClass`, the expected `FailureAction`, the expected status label, the expected comment body and the injection that installs the fault. Build `FAULT_CASES` with one case for each of the nineteen classes: a provider HTTP 500, a malformed tool call, an exit status 143, an exit status 137, a non-fast-forward push, a failing pytest log, a failing ruff log, a failing mypy log, an unticked task group, a false premise, a refused command, a check whose log shows nothing, a fix step that changes no file, a lost test, a moved head, an output cap, a read-only path, a reached limit and a change outside the plan. Each case runs the job through `JobWorld.run` on `job_world`, then asserts the stop is the item's, the class in the job record, `ACTION_BY_CLASS[case.klass] is case.action`, the final label `status/blocked`, the exact comment body, and the kept work: the branch, the `wip:` commit or the draft pull request. Add `test_every_failure_class_has_a_fault_case`, which compares the case classes with `set(FailureClass)` and names each missing class, and `test_the_fault_suite_has_at_least_twelve_cases`, which asserts the table holds at least 12 cases
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_faults.py` passes

## 2. Add the Service state-file fault cases

Reads: `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/output/file_writer.py`, `tests/roadmap/test_roadmap_run_failure_ledger.py`, `tests/roadmap/test_roadmap_run_service.py`. Changes: `tests/roadmap/test_roadmap_run_state_faults.py` (new).

- [ ] 2.1 Add `tests/roadmap/test_roadmap_run_state_faults.py` with four cases, each on a path under `tmp_path`. A halt record that cannot be written: write a regular file at `tmp_path / "blocker"`, give `RoundPause` the record `tmp_path / "blocker" / "service-halt.json"` and a refusal reader that answers True, then call `after`; the record does not exist at construction, the write raises `NotADirectoryError`, one `state_unkept` error line names the record and that class, `halted()` is True, the next round starts nothing, and no record file exists. An unreadable `schedule.json`: the bytes are not JSON, `_read_schedule` returns no time, the row runs, and `_record_success` writes a valid file with the job's time. An unreadable failure ledger: `FailureLedger(record=path)` raises `RoadmapRunError` naming the file and the remedy. An unreadable intake record: `read_intake_record(path)` raises `RoadmapRunError` naming the file and the remedy. Each case asserts the injected error class, the row result, the final state and that the earlier record is kept
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_state_faults.py` passes

## 3. Add the Service row fault cases

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/support/roadmap_run.py`, `tests/support/roadmap_stage.py`, `tests/roadmap/test_roadmap_run_intake_row.py`, `tests/roadmap/intake/test_roadmap_intake_github_requests.py`. Changes: `tests/roadmap/test_roadmap_run_row_faults.py` (new).

- [ ] 3.1 Add `tests/roadmap/test_roadmap_run_row_faults.py` with three cases on `lane_table`, `poll_round` and `apply_stage`. A `RoadmapItemChangedError` during intake apply: `fail_write(write="label_issue", error=RoadmapItemChangedError(...))` leaves the person's `priority/p1-high` label in place, counts the candidate as failed, raises the round error that names the item and `RoadmapItemChangedError`, and keeps the earlier placement record. A Service stop between two stage items: the second item's write raises `ServiceStoppingError`, the first item's stage record and branch stay, and the round ends as a stop and not as a failed round. A failed marks write after the draft pull request exists: `fail_write(write="set_marks", at=1)` makes the `set_marks` call that follows the pull request open raise `GitHubOperationError`, and `write_each` catches it as a plain `DevOpsCLIError` and records a `StageFailure` whose error class is `GitHubOperationError` and whose reason is the masked error message. The branch and the draft pull request stay on origin, the item posts no staged comment, and the item counts as failed in the row. Each case asserts the injected error class, the row result, the final status label, the failure record or the round error text, and the kept work
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_row_faults.py` passes

## Criteria

- Group 1: At least 12 fault cases run offline in the test suite in under a stated time.
- Group 1: Each case asserts the final status label and the comment text.
- Group 1: Adding a failure class needs a case (a test checks that every class has one).
- Group 3: The suite adds no more than 60 seconds to the test check.
