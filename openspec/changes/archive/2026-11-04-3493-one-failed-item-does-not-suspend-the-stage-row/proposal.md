# Proposal

## Why

Issue #3493: one failed item can suspend the `stage` row of a whole repository. The adapter of the row calls `raise_for_failed` after it writes the staged items, so a round that staged an item still fails when another item failed. The ledger of failed rounds counts such a round. Below its limit it also counts a failure on another input, so three rounds that each fail on a different item suspend the row. A suspended row plans no item until its input changes. The causes of the failed rounds stay in memory, so after a restart the log line of a suspension names them `unknown`. A stop of the Service at shutdown leaves the ledger alone, but the Service still logs an ERROR line and counts the round as `error`.

The alternatives row got the right form in #2949: the failure goes into the job record of the item, the item waits for a delay, and the row fails only when it tried items and checked none. The change gives the stage row the same form.

## What Changes

- A failed item (a failed model call, a refused reply, a failed validation, or a failed write) is recorded in its job record with two new keys: `stage.failed_at` and `stage.failed_error`. `apply_stage` writes them, also when a stop of the Service ends the run. A run that stages the item or stops it on the budget clears both keys.
- The selection leaves out an item whose `stage.failed_at` is younger than the new setting `roadmap.stage.retry_hours` (integer of at least 1, default 6). `--item` still takes the item it names. `devops roadmap explain` reads the same selection, so it reports the held item and the time of its retry from the job record on GitHub.
- The row fails a round only when the round tried items and staged, stopped on the budget or returned none, through the new `raise_for_failed_round`. A failure that no item explains, such as an outage, still raises and counts. `devops roadmap stage --confirm` keeps `raise_for_failed`, so its exit code is still 1 after any failed item.
- `apply_stage` no longer raises the failed items when a stop ends the run. It records them and re-raises the stop. The row then counts nothing for that round.
- The ledger record holds the causes of each job: an entry is `[repo, job, rounds, input, causes]`. A record of four fields still loads, and its causes read as `unknown`.
- `ended_by_stop` moves to `devops_cli.exceptions` next to `ServiceStoppingError`, so the Service and the roadmap code share it. A scoped update or a round that a stop ends counts as `result="stopped"` in `devops_cli_service_jobs_total`, is the `stopped` result of the last round, logs one info line, and does not pause the lane.
- The change carries a spec delta: it has consumer-observable behavior (a setting, a job record key, a metric result and the `explain` output).
- Code the change deletes: the rule "any failed item fails the round" in `_run_stage_adapter`, the note that keeps the causes in memory, and the stage branch of the stop path in `apply_stage` that raised the failed items.
- The change fits one pull request. It has four task groups: the record and the delay, the rule of the row, the ledger, and the stop result.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: a failed item is recorded and waits; the row fails only when it handled no item.
- `roadmap-explain`: the command reports an item that the stage job holds for a retry.
- `roadmap-service-limits`: the ledger keeps its causes across a restart; a round that a stop ends counts as `stopped` and logs no error.

## Impact

- Code: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_stage_retry.py` (new), `tests/roadmap/test_roadmap_stage_job.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_run.py`, `tests/server/test_server_service.py`, and the import of `ended_by_stop` in `tests/roadmap/test_roadmap_refine.py`.
- Documents: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`, `k8s/README.md`, and the generated `docs/CONFIGURATION.md`.
- Existing code to keep and reuse: `FailureLedger`, `StageFailure`, `ended_by_stop`, `RoadmapStore.set_marks`, and the form of `alternatives.py` (`_in_retry_delay`, `apply_alternatives`, `raise_for_failed_checks`).
- The ledger file changes its format. A Service of an older version cannot read the new file; remove `service_failures.json` before such a rollback. Pre-1.0 software keeps no compatibility for that.

## Acceptance

- Three rounds that fail one item while another stages do not suspend the row: group 2.
- Three rounds that try items and plan none suspend the row: group 2.
- A failure outside any item suspends the row: group 2.
- The job record of a failed item holds the error class and the time, and the job takes the item again after the delay: group 1.
- `devops roadmap explain` reports a held item from the job record: group 1.
- The ledger record holds the causes, and a record in the old format loads: group 3.
- A scoped update that a stop ends counts as `stopped` and logs no ERROR line: group 4.

## Feasibility

All checks ran on 2026-11-04 in a worktree at `origin/main` (67d3f473).

- The mechanism is as the issue says. `git grep -n "raise_for_failed" -- src/devops_cli/roadmap/run.py` showed `_run_stage_adapter` raising every item failure after the write. `FailureLedger.failed` incremented the count whenever `rounds < limit`, whatever the input, so failures on different items added up.
- The causes were in memory only: the old `FailureLedger` docstring said so, and `_FailedRounds` was a list of four-field tuples.
- A stop reached `service.py` as an `Exception`: `_execute_scoped` and `_execute_batch` set `result = "error"` and logged at ERROR for every exception, and `ended_by_stop` was only used by `_count_failure`.
- The record on GitHub is readable by `explain`: `explain_item` calls `read_stage_selection`, which judges `item.job_record`, so one rule in the judge serves the job and the command.
- A skip without a time limit is unsafe: the issue shows that #3393 and #3404 failed several rounds and later got plans. The delay is a time, not a permanent skip.
- Nothing newer did or removed the work: `git log --oneline -5 -- src/devops_cli/roadmap/stage.py` shows no commit that records stage failures in the job record.

## Existing Tool Considered

No open, maintained tool covers a per-item failure record inside the stage row of this roadmap Service. The change reuses the form that #2949 gave the alternatives row, `FailureLedger`, `StageFailure`, `ended_by_stop`, and `RoadmapStore.set_marks`. It adds no new store, no scheduler and no library. The written cost is about 40,000 tokens to build and test, small upkeep because every part reuses existing code, and about half a day of elapsed time to pass `uv run devops ci`.
