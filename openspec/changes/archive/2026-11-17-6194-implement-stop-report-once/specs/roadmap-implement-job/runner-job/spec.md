## MODIFIED Requirements

### Requirement: A later round reports the Job that ended
A round SHALL read the Job of each item whose record holds `implement.job` and no `implement.job_state`. It SHALL record `implement.job_state` as `succeeded` or `failed` for a Job that ended (Complete or Failed), and as `gone` for a Job that no longer exists. Its comment on the item SHALL hold the marker of the implement job, the state and the last lines of the pod's log, decoded and masked of secrets, in a fenced block. A log that the API refuses SHALL not block the report.

#### Scenario: A log with a check mark and several lines
- **WHEN** the log of the pod of a Job that left no result is the bytes of two lines, the first with a check mark and the second with a token
- **THEN** the comment holds a fenced block with the two lines on two lines, the check mark as the character, the token masked, and no `b'` prefix

#### Scenario: A log with a run of backticks
- **WHEN** a line of the log of a Job that left no result holds a run of three backticks
- **THEN** the fence of the block is longer than that run

#### Scenario: A log the API refuses
- **WHEN** the API refuses to read the log of the pod of a Job that failed and left no result
- **THEN** the item gets the comment without a log, `implement.job_state` is `failed`, and the next round raises no error

#### Scenario: A Job that is gone
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** `implement.job_state` is `gone`, and the item gets a comment that the Job no longer exists

## ADDED Requirements

### Requirement: The round comments only on a Job that left no result
The round SHALL comment on the item only for a Job whose runner left no result, or for a Job that is gone. A Job whose runner wrote its result, a stop included, SHALL get no comment: the comment of the runner is the report of the run, and the record holds the state and the digest of the Job.

#### Scenario: A Job that succeeded
- **WHEN** the Job of an item has the condition Complete, the item is In Review, and the record holds `implement.result` equal to `ready`
- **THEN** the item gets no comment, `implement.job_state` is `succeeded`, and the Status stays In Review

#### Scenario: A Job whose runner wrote its stop
- **WHEN** the Job of an item has the condition Failed, and its runner set the item Blocked with `implement.stopped` and `implement.result` equal to `stopped`
- **THEN** the item gets no comment, and `implement.job_state` is `failed`
