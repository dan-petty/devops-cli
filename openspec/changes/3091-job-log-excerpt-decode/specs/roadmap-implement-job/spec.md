## MODIFIED Requirements

### Requirement: A later round reports the Job that ended
A round SHALL read the Job of each item whose record holds `implement.job` and no `implement.job_state`. For a Job that ended (Complete or Failed), it SHALL comment on the item, with the marker of the implement job, the state and the last lines of the pod's log, and record `implement.job_state` as `succeeded` or `failed`. The round SHALL decode the log as UTF-8 text with real line breaks, mask secrets in the decoded text, and show it in a fenced block whose fence is longer than any run of backticks in the text. A Job that no longer exists SHALL be recorded as `gone`. A log that the API refuses SHALL not block the report.

#### Scenario: A Job that succeeded
- **WHEN** the Job of an item has the condition Complete and the item is In Review
- **THEN** the item gets a comment with the state `succeeded`, `implement.job_state` is `succeeded`, and the Status stays In Review

#### Scenario: A log with a check mark and several lines
- **WHEN** the log of the pod is the bytes of two lines, the first with a check mark and the second with a token
- **THEN** the comment holds a fenced block with the two lines on two lines, the check mark as the character, the token masked, and no `b'` prefix

#### Scenario: A log with a run of backticks
- **WHEN** a line of the log holds a run of three backticks
- **THEN** the fence of the block is longer than that run

#### Scenario: A log the API refuses
- **WHEN** the API refuses to read the log of the pod of a Job that failed
- **THEN** the item gets the comment without a log, `implement.job_state` is `failed`, and the next round raises no error

#### Scenario: A Job that is gone
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** `implement.job_state` is `gone`
