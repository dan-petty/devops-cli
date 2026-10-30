# Proposal

## Why

Issue #2753: a round that ends because the Service is stopping counts as a failed round. Three failed rounds in a row suspend the row of a repository, so it does not run again until its input changes. Releases and rollouts restart the Service several times in a few hours. A row can be suspended with no real failure.

The Service log of 2026-10-30 shows it. The `refine` and `implement` rows of one repository failed with the stop error of the request budget, and the log then said that the roadmap job failed 3 rounds in a row. The Service keeps the count in `service-failures.json` on its volume, so a restart does not clear it.

## What Changes

- The error that the budget raises when the Service is stopping gets its own class, `ServiceStoppingError`, a subclass of `RoadmapRunError`. `RequestBudget.admit` raises it. No code reads the message of the error.
- A round of a row that ends with this error, or with an error that has it as its cause, is not a failure. `FailureLedger` keeps the count of its row as it was: it does not add 1, does not clear it, and does not suspend the row. The round still ends with its error, and the log still shows it.
- The stage job lets this error pass, as it lets rejected GitHub credentials pass. Before, it made a failed write of an item out of it, and the round counted as a failure.
- `FailureLedger` keeps the class of the error of each failed round, for the rounds that count. The log line that suspends a row names the cause of each of the rounds in a row.
- The file `service-failures.json` keeps its format. The causes are kept in the memory of the process.
- A comment by a person on an item of a suspended row does not start the row again today. This change does not alter that. The follow-up issue #2754 tracks it (see Feasibility).

## Capabilities

### Modified Capabilities

- `roadmap-service-limits`: a stop is not a failed round, and the line that suspends a row names the causes.

## Impact

- `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/exceptions/__init__.py`
- `src/devops_cli/server/service.py`
- `src/devops_cli/roadmap/run.py`
- `src/devops_cli/roadmap/stage.py`
- `src/devops_cli/lang/en/messages.py`
- `tests/test_service_limits.py`, `tests/test_roadmap_stage_apply.py`
- `openspec/specs/roadmap-service-limits/spec.md`
- The change fits one pull request.

## Feasibility

- **The class of the stop today.** `RequestBudget.admit` raises `RoadmapRunError(MESSAGES.serve.budget_closed...)` (`src/devops_cli/server/service.py`). `RoadmapRunError` is also the class of the round error (`_execute_due_rows`) and of an unreadable state record (`read_state_record`). So the class alone does not name a stop. A subclass does, and `isinstance` reads it. Verified by the test `test_a_request_the_budget_has_no_room_for_ends_when_the_budget_is_closed`, which now asserts the new class.
- **Where the ledger counts a failure.** One place: the `except Exception` branch of `_execute_due_rows` in `src/devops_cli/roadmap/run.py` calls `_count_failure`, which calls `FailureLedger.failed`. `FailureLedger.suspended` reads the count at the next round. `succeeded` clears it.
- **How the stop reaches the branch.** The gate runs in `GitHubRateLimiter.acquire`, before the request. In the refine, implement, intake and alternatives rows nothing between the gate and the row catches `DevOpsCLIError`, and the log of 2026-10-30 shows the raw message in the round error. In the stage job, `_write_each` catches `DevOpsCLIError` and makes a `StageFailure` with no cause (`_write_failure`), so the stop is lost. The change makes `_write_each` let `ServiceStoppingError` pass. `_implement_item` also catches `DevOpsCLIError`, but it runs in the runner Job, which has no gate, so the Service never sees it.
- **The file format.** `service-failures.json` is a list of `[repo, job, rounds, input]` records. The running version reads it with `TypeAdapter(list[tuple[str, str, int, str]])`, and `read_state_record` raises when a record cannot be read, so the Service would refuse to start. A tuple of another length fails that check. So the change adds no field to the file. The test `test_the_ledger_file_keeps_the_format_that_the_running_version_reads` writes a ledger, reads the file with the exact adapter of the running version, and loads a record in the old format with the new code.
- **A comment on an item of a suspended row.** It does not clear the suspension. The input of a round (`_round_input`) is a digest of the issue events since the last success (`ChangeKind`: labeled, unlabeled, closed, reopened) and, for a trigger that is not a poll, the time of the round. The issue events carry no comment. The Service takes only the `issues` webhook event (`CONST_ROADMAP_WEBHOOK_EVENTS`, and "only the Issues event" in `k8s/README.md`), so an `issue_comment` delivery gets `no_subscriber`. ADR 0009 dropped that event on purpose, after #1361 measured 940 triggers in one hour. A fix needs a new subscription on each repository hook, which a person changes, or a comment read at each poll, which costs requests. This is not a small change, so it is not part of this pull request. Follow-up: #2754. The first two points of this change remove the cause of the lost retry that the issue names: a stopped round no longer suspends its row.
- **The Service volume.** No change to a file, a manifest or the cluster is needed.

## Existing Tool Considered

The typed error of the budget is the tool: the change gives it a class and reads that class with `isinstance`. Python's exception groups and `__cause__` chain carry it through the round error, and `identity_refused` already reads them the same way. Nothing new is built, and the change deletes no code.
