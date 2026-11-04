# Design

## Decisions

- **The failure record is two keys in the job record of the item.** `stage.failed_at` holds an ISO time and `stage.failed_error` holds the class of the error. `explain` reads GitHub and git and cannot read a file on the Service volume, so the record lives on the issue, as in #2949. `StageFailure` gets an optional `item` field (not part of its equality), so `apply_stage` can write the record without a second read of the issue.
- **`apply_stage` records the failures, for the row and for the command.** The command `devops roadmap stage --confirm` then also holds a failed item for the delay, and a person can still take it with `--item`.
- **The delay is judged in the selection.** `_Judge._failed_lately` leaves out an item whose failure is younger than `roadmap.stage.retry_hours`. The check runs for `--plan` and for `explain` through the same `select_stageable`, and it is skipped when a person names the item. A value that is no time is logged and ignored, as `alternatives.py` does.
- **The default delay is 6 hours.** The row runs every 37 minutes. A delay of 6 hours gives a provider outage time to end and costs a failing item one try in about 10 rounds. The issue names no number. The value is a setting named in hours because the row runs many times a day.
- **The row fails when the round handled no item.** `raise_for_failed_round` returns when the round staged, stopped or returned an item, because the model and GitHub then worked. When the round tried items and handled none, it raises the failures, as before. This also fixes a round that staged an item and still counted as failed. The status-sync failure keeps its own `raise_for_failed`, as it does not belong to one item.
- **A stop ends the run after the record.** `apply_stage` catches `ServiceStoppingError`, records the failures found so far, and re-raises the stop. The row ends with the stop and counts nothing. The old rule raised the failed items instead, which counted a round that a stop ended.
- **The ledger record gets a fifth field.** An entry is `[repo, job, rounds, input, causes]`. The adapter accepts both four and five fields, so a record of an older version loads, and its causes read as `unknown` through the existing fill in `causes()`.
- **`ended_by_stop` moves to `devops_cli.exceptions`.** It belongs next to `ServiceStoppingError`, and `server/service.py` cannot import the roadmap package without a cycle risk. `run.py` and the tests import it from the new place; no shim stays.
- **A round that a stop ends is `stopped`.** `_execute_scoped` and `_execute_batch` ask `ended_by_stop` first. For a stop, `RepoWorker._end_in_stop` logs one info line and the result is `stopped`; the block does not call `pause.after`. For any other error each block behaves as before.

## Rejected alternatives

- **Reset the row ledger after any success.** A later success would hide an unexplained outage; the row must still suspend on failures that no item explains.
- **Skip a failed item for ever.** #3393 and #3404 failed 5 and 4 rounds and later got plans.
- **A file on the Service volume for the item failures.** `explain` cannot read it.
- **Reuse `roadmap.alternatives.retry_days`.** It couples two rows and counts days, which is too long for a row that runs every 37 minutes.
- **A second stop detector in the Service.** Two detectors can disagree. `ended_by_stop` already reads the shapes that the ledger needs.
- **Keep causes in memory.** A restart makes every cause `unknown`, which is the symptom in the issue.
