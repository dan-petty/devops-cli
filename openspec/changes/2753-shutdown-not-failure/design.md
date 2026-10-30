# Design

## Decisions

- **A subclass of `RoadmapRunError`.** `ServiceStoppingError` extends `RoadmapRunError`, so each `except RoadmapRunError` and each `isinstance` that exists keeps its result. Its `error_code` is `SERVICE_STOPPING`. The budget keeps its message and its `details` (`limit`).
- **One reader: `ended_by_stop`.** It sits beside `identity_refused` in `roadmap/run.py` and reads the same shapes: the error itself, an exception group, and the `__cause__` chain. For a group, every member must be a stop. A group that holds a real failure is a failure. It reads `__cause__` and not `__context__`, because the context of an error is only what happened to be handled when it was raised.
- **The count stays as it was.** On a stop, `_execute_due_rows` does not call `_count_failure`. The row still enters `failed_jobs`, so the round still ends with its error, and the log still shows what ended it. The row has no success, so `schedule.json` is unchanged and the next round finds the row due again. The count neither grows nor clears: a row at 2 failed rounds stays at 2, and one real failure after the restart suspends it, as before.
- **Causes are in memory.** `FailureLedger.failed` takes the class name of the error and keeps the last `limit` causes of the row. A cause is typed data (`type(exc).__name__`), not text from the message. The causes restart with the count: a failure on new input starts a new list, and a success clears it. A process that starts with a count of rounds from the file knows no cause for the rounds before it, and the log line says `unknown` for them.
- **The file does not change.** The running version reads each record as a 4-tuple, and a longer tuple makes `read_state_record` raise. A rollback after the deploy must start. So the format stays, and the new code reads the old file as it is.
- **The line that suspends a row.** `MESSAGES.serve.job_suspended` gets a `{causes}` field: `... failed 3 rounds in a row (causes: A, B, C), so it does not run again until its input changes.`
- **The stage job.** `_write_each` re-raises `ServiceStoppingError` with the credentials error. The write that was stopped is not a failed item, and the next write would meet the same closed gate.
- **No change to the retry by comment.** See Feasibility. The follow-up is #2754.

## Rejected alternatives

- **Match the message text.** The message says "the Service is stopping". The text belongs to `lang/en/messages.py` and changes with the wording. A class is the typed seam.
- **Ask the budget whether it is closed.** `RequestBudget.closed` at the time of the failure would also hide a real failure that happens as the pod stops, and the ledger would depend on the budget. The class names the error that the stop caused.
- **Add `causes` to `service-failures.json`.** The running version cannot read a record of another length, and the Service would not start after a rollback. A second file for the causes adds a record to keep and to read for a log line.
- **Clear the count on a stop.** A row that failed twice for a real reason would restart at 0 after each deploy, and a row that never works would never suspend.
- **Do not raise from the round on a stop.** The round did not finish its work. Ending with its error keeps the log and the `result="error"` count honest, and costs nothing, as the pod is stopping.
- **Subscribe to `issue_comment` here.** It needs each repository hook to send the event, and ADR 0009 dropped it after #1361 measured 940 triggers in one hour. It is a larger change with its own measure of requests: #2754.
