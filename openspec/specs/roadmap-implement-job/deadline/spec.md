# roadmap-implement-job/deadline Specification

## Purpose
The deadline of a runner Job: the short first deadline, the progress events that extend it, the stall time and the ceiling, and the continuation of a Job that ended without a result.

## Requirements

### Requirement: A runner Job starts with a short deadline and an annotation
The Service SHALL create the runner Job with `activeDeadlineSeconds` equal to `roadmap.implement.deadline_extension_seconds` and the annotation `roadmap.devops-cli/progress-at`. A Job that the Service did not annotate SHALL keep its deadline.

#### Scenario: A created Job
- **WHEN** a round creates the Job of an item
- **THEN** the Job spec holds the extension step as `activeDeadlineSeconds` and the annotation holds the time of the create

#### Scenario: A Job without the annotation
- **WHEN** a Job of the repository has no annotation `roadmap.devops-cli/progress-at` and its log changes
- **THEN** the Service patches nothing

### Requirement: A changed log is a progress event
In each round, for each annotated Job of the repository that has not ended and has a start time, the Service SHALL compare the digest of the last lines of its log with the annotation `roadmap.devops-cli/progress`. A digest that differs is a progress event. An empty log, or a log that the API refuses, SHALL NOT be a progress event.

#### Scenario: A log that changed
- **WHEN** the last lines of the log of an annotated Job differ from the lines of the last round
- **THEN** the Service stores the new digest and the time in the annotations

#### Scenario: A log the API refuses
- **WHEN** the API refuses to read the log of an annotated Job
- **THEN** the round raises no error and makes no progress event

#### Scenario: A Job whose pod has not started
- **WHEN** a Job of the repository has no start time
- **THEN** the Service patches nothing

### Requirement: A progress event extends the deadline
On a progress event the Service SHALL set `activeDeadlineSeconds` to the smaller of the ceiling and the greater of the deadline in force and the seconds since the Job started plus the extension step, and SHALL store the digest and the time in the annotations.

#### Scenario: A replay that makes progress for three hours
- **WHEN** the Job log changes before each round for three hours of the faked clock, with the default settings
- **THEN** the Job is not past its deadline at any round, and `activeDeadlineSeconds` is never above the ceiling

#### Scenario: The Job spec shows the deadline
- **WHEN** a round saw progress at 1800 seconds after the Job started, with an extension of 3600
- **THEN** the Job spec holds `activeDeadlineSeconds` 5400

#### Scenario: The deadline stops at the ceiling
- **WHEN** a progress event comes at a time where the start plus the extension is above the ceiling
- **THEN** `activeDeadlineSeconds` equals the ceiling

#### Scenario: The deadline never goes down on progress
- **WHEN** a progress event comes while `activeDeadlineSeconds` is above the start plus the extension
- **THEN** the Job keeps its deadline

### Requirement: A run that makes no progress ends at the stall time
When the log of an annotated Job has not changed for `roadmap.implement.deadline_stall_seconds`, measured from the time in `roadmap.devops-cli/progress-at`, the Service SHALL set `activeDeadlineSeconds` to the seconds since the Job started, set the annotation `roadmap.devops-cli/stalled`, and log the stall. The Job controller then ends the Job. The report comment of a Job that has the annotation SHALL say that the Job stalled and name the stall time.

#### Scenario: A replay that makes none
- **WHEN** the Job log does not change for the stall time and a round runs
- **THEN** the Job spec holds a deadline equal to the seconds since the start, and the annotation `roadmap.devops-cli/stalled` is set

#### Scenario: A silent wait below the stall time
- **WHEN** the Job log does not change for less than the stall time
- **THEN** the Service changes no deadline

#### Scenario: An empty log
- **WHEN** the Job log is empty and the stall time has not passed
- **THEN** the Service changes no deadline

#### Scenario: The report names the stall
- **WHEN** a round reports a Job that ended and has the annotation `roadmap.devops-cli/stalled`
- **THEN** the comment on the item names the stall time

### Requirement: The trace shows each deadline change
Each extension and each stall SHALL be a span `implement.deadline` with the attributes `job`, `deadline.previous_seconds`, `deadline.seconds` and `reason`. The reason SHALL be `progress`, `progress, ceiling` or `stall`. A progress event that changes no deadline SHALL make no span.

#### Scenario: An extension
- **WHEN** a round extends the deadline of a Job
- **THEN** the tracer sends a span `implement.deadline` with the Job name, the old and the new deadline and the reason `progress`

#### Scenario: A stall
- **WHEN** a round ends a Job for a stall
- **THEN** the tracer sends a span `implement.deadline` with the reason `stall`

### Requirement: The extension, the stall and the ceiling are settings
The settings `roadmap.implement.deadline_stall_seconds` (default 4200), `roadmap.implement.deadline_extension_seconds` (default 5400) and `roadmap.implement.deadline_ceiling_seconds` (default 14400) SHALL set the stall time, the extension step and the ceiling, and each SHALL have an environment variable. The configuration SHALL refuse a stall above the extension, an extension above the ceiling, and a ceiling above 14400.

#### Scenario: The defaults
- **WHEN** the configuration is loaded with no value for the three settings
- **THEN** they are 4200, 5400 and 14400

#### Scenario: A stall above the extension
- **WHEN** the stall is set above the extension
- **THEN** the configuration is refused

#### Scenario: A ceiling above the cap
- **WHEN** the ceiling is set to 14401
- **THEN** the configuration is refused

### Requirement: The default stall covers the silent waits of the runner
The default stall SHALL be at least 600 seconds above the longest wait in which the runner writes no log line, and the default extension SHALL be at least the stall plus the interval of the `implement` row plus the interval of a tick of the Service.

#### Scenario: The defaults cover the silent waits
- **WHEN** a test reads the constants of the runner
- **THEN** the default stall is at least the longest of the command timeout, the model call timeout and the monitor timeout plus 600 seconds, and the default extension is at least the stall plus the interval of the row and the tick of the Service

### Requirement: The Service continues a Job that ended without a result
A round SHALL clear the stop of an item with the rule `continue` when `implement.stopped` is `job`, the class in `implement.failure` has the action `retry` in `ACTION_BY_CLASS`, and `implement.continuations` is less than `roadmap.implement.continuations_per_item`. A clear SHALL remove `implement.stopped`, `implement.failure` and the failed check, and set the Status to Ready or Planned.

#### Scenario: A Job that was killed
- **WHEN** the Job of an item ended Failed with no result, its log shows no known cause, and `implement.continuations` is not set
- **THEN** the round reports the Job and sets `implement.stopped` to `job` and the class to `ci_infra`
- **AND** the round clears the stop by the rule `continue` and makes a new Job for the same item that takes the branch from `origin`

#### Scenario: A Job that the Service ended by its stall
- **WHEN** the Service ended a Job by its stall and the report gives the class `timeout`
- **THEN** the round continues the item

#### Scenario: A Job that no longer exists
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** the round reports the state `gone` and continues the item

#### Scenario: A class that a new attempt cannot fix
- **WHEN** the log of the Job that ended with no result shows an out-of-memory kill, so the class is `oom` with the action `raise_limit`
- **THEN** the item stays Blocked, `implement.continuations` is not set, and the API receives no Job create until a comment `implement: retry`

#### Scenario: An out-of-memory kill that the log does not show
- **WHEN** a Job ends with no result and its log holds no sign of a memory limit
- **THEN** the class is `ci_infra` and the round continues the item, because the Service reads no pod status

#### Scenario: A stop that the runner wrote
- **WHEN** an item is Blocked with `implement.stopped` as `group 1` and the class `provider`
- **THEN** the rule `continue` does not clear it

### Requirement: The continuations of an item are a setting
The setting `roadmap.implement.continuations_per_item` SHALL default to 2, SHALL refuse a count below 0, and SHALL turn the rule `continue` off at 0.

#### Scenario: The default
- **WHEN** no config file and no variable set the value
- **THEN** `roadmap.implement.continuations_per_item` is 2

#### Scenario: The limit is 0
- **WHEN** `roadmap.implement.continuations_per_item` is 0 and the Job of an item ends with no result
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A negative count
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_CONTINUATIONS_PER_ITEM` is -1
- **THEN** the load of the settings fails with an error that says the value must be greater than or equal to 0

### Requirement: A continuation is counted
A continuation SHALL set `implement.continuations` to the old count plus 1. The record SHALL hold a count and no other data. The count SHALL stay after a clear, and a comment `implement: retry` SHALL NOT reset it.

#### Scenario: No continuation is left
- **WHEN** a Job with a continuation count of 2 ends with no result, and ten rounds run
- **THEN** the item stays Blocked with `implement.stopped` as `job` and the API receives no Job create
- **AND** a comment `implement: retry` of the owner still clears the stop

#### Scenario: A new image at the limit
- **WHEN** the continuation count is at the limit and the template names a digest that differs from `implement.job_digest`
- **THEN** the rule `digest` clears the stop within its own limits, and `implement.continuations` is unchanged

#### Scenario: A count that is not a count
- **WHEN** `implement.continuations` holds `two`, `-1` or `1.5`
- **THEN** the rule `continue` does not clear the stop, the round does not fail, and a comment `implement: retry` still clears the stop

### Requirement: The comment of a continuation says how many are used
The comment of a continuation SHALL name the rule, the Job and the class, and SHALL say "continuation n of N". At the last continuation it SHALL also say "No continuation is left".

#### Scenario: The first continuation
- **WHEN** the rule `continue` clears a stop and `implement.continuations` is not set
- **THEN** `implement.continuations` is 1, the comment says "continuation 1 of 2", and the comment does not say "No continuation is left"

#### Scenario: The last continuation
- **WHEN** a Job with a continuation count of 1 ends with no result and its class has the action `retry`
- **THEN** the round records `implement.continuations` as 2, comments "continuation 2 of 2" and "No continuation is left", and makes a new Job

### Requirement: A continuation spends no clear by digest
The rule `continue` SHALL run before the rule `digest`, SHALL read no template and SHALL add no entry to `implement.digest_clears`.

#### Scenario: A continuation and a new image
- **WHEN** a Job ends with no result and the template names a new digest
- **THEN** the round clears the stop by the rule `continue`, `implement.digest_clears` is not set, and the new Job records the new digest in `implement.job_digest`

### Requirement: The report of a Job with no result says what the Service does next
The report of a Job with no result SHALL say that the Service starts a new Job when a retry can fix the class of the stop. It SHALL name the setting `roadmap.implement.continuations_per_item` and the comment `implement: retry`. It SHALL say that a new runner image also clears the stop within its limits.

#### Scenario: A Job that failed
- **WHEN** the round reports a Job that ended Failed and left its item In Progress
- **THEN** the comment names the setting `roadmap.implement.continuations_per_item` and the comment `implement: retry`
