# Design

## Decisions

- **Set the gauge inside `keep_state_record`.**: All four writes go through this one function, so one place sets the gauge for the three records. A caller cannot forget it.
- **The kind is a `StateRecord` string enum, not a free string.**: A typo in a label value would make a new series that the alert still selects but that a person cannot match to a record. The enum has three values, and mypy checks each call site.
- **The gauge is 1 after a write error and 0 after the next good write, and the first write creates the series.**: A series is created by the first write of its record. The `halt` series exists only after a halt record is written, which is rare. The alert is `max by (record) (...) > 0`, so it needs no series at 0.
- **No priming at 0 at start.**: The alert needs no series at 0, and a gauge at 0 for a record that was never written would say that the record is kept. The three series exist after each record is written once.
- **Keep the log line, and do not raise.**: `RequestBudget.admit` calls the function for every admitted request. A raise would stop all work for a disk fault (#2474). A first plan of the issue made the next round start fail for a halt or ledger fault; it is dropped, because a disk fault must not stop all work.
- **The alert waits 15 minutes and reads `max by (record)` of the gauge of the job `roadmap-service`.**: A fault that the next write repairs does not alert. The selector has `job="roadmap-service"`, as every selector of the group does, so a workstation's series never counts.
- **The alert is in the group `roadmap-service`.**: The gauge is a series of the Service's `/metrics`, like `devops_cli_service_job_suspended`, and the group has the alerts of the Service's own state.

## Rejected alternatives

- **Fail the next round start after a halt or ledger write error.**: A disk fault would stop all work, and the issue drops it. The gauge and the alert give the signal.
- **Raise from `keep_state_record`.**: `admit` calls it for every request, and the record is a log of what memory holds. A raise would stop the request path (#2474).
- **Count write errors with a counter and alert on `increase`.**: A counter shows that a write failed some time ago, not that the record is unkept now. After a repair the alert would still fire for the window. The gauge goes to 0 at the next good write.
- **Prime the three series at 0 when the Service starts.**: See above: a 0 for a record that was never written is a claim that nothing supports, and the alert gains nothing from it.
- **A new alert group.**: One alert fits the existing group, and the rule-test machinery already runs that group.
