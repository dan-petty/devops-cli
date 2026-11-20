## MODIFIED Requirements

### Requirement: A Job that leaves its item eligible stops the item
When a reported Job leaves its item neither In Review nor stopped, and the record holds no `implement.result` of `drafted`, `yielded` or `returned`, the round SHALL set the item Blocked and record `implement.stopped` as `job`. No Job SHALL be created for the item before a clear rule runs.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed, the item is In Progress, the record holds no `implement.result`, and no continuation applies to it
- **THEN** the item gets a comment with the state `failed` and the tail of the log
- **AND** `implement.job_state` is `failed`, the Status is Blocked, and `implement.stopped` is `job`
- **AND** the next round creates no Job for the item

### Requirement: The report reads the result of a Job
The round SHALL read `implement.result` when it reports a Job that ended. A Job with the result `drafted`, `yielded` or `returned` SHALL cause no stop of the item. A Job with no result SHALL get its stop and its class from the Status of the item and the tail of its log, with `classify_failure`.

#### Scenario: A yielded Job
- **WHEN** the Job of an item ended, the item is In Progress, and the record holds `implement.result` equal to `yielded`
- **THEN** the round records `implement.job_state`, sets no Status, and records no `implement.stopped`

#### Scenario: A Job with no result
- **WHEN** the Job of an item failed, the item is In Progress, the record holds no result, and the log holds an out-of-memory line
- **THEN** the round records the class `oom` and sets the item Blocked

### Requirement: The round comments only on a Job that left no result
The round SHALL comment on the item only for a Job whose runner left no result, or for a Job that is gone. A Job whose runner wrote its result, a stop included, SHALL get no comment: the comment of the runner is the report of the run, and the record holds the state and the digest of the Job.

#### Scenario: A Job that succeeded
- **WHEN** the Job of an item has the condition Complete, the item is In Review, and the record holds `implement.result` equal to `drafted`
- **THEN** the item gets no comment, `implement.job_state` is `succeeded`, and the Status stays In Review

#### Scenario: A Job whose runner wrote its stop
- **WHEN** the Job of an item has the condition Failed, and its runner set the item Blocked with `implement.stopped` and `implement.result` equal to `stopped`
- **THEN** the item gets no comment, and `implement.job_state` is `failed`
