## ADDED Requirements

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
The settings `roadmap.implement.deadline_stall_seconds` (default 2400), `roadmap.implement.deadline_extension_seconds` (default 3600) and `roadmap.implement.deadline_ceiling_seconds` (default 14400) SHALL set the stall time, the extension step and the ceiling, and each SHALL have an environment variable. The configuration SHALL refuse a stall above the extension, an extension above the ceiling, and a ceiling above 14400.

#### Scenario: The defaults
- **WHEN** the configuration is loaded with no value for the three settings
- **THEN** they are 2400, 3600 and 14400

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

### Requirement: The memory limit of a runner Job stays 8 Gi
The runner Job SHALL have the memory limit of the CronJob template, 8 Gi, whatever the deadline settings are.

#### Scenario: The memory limit
- **WHEN** a round creates a Job
- **THEN** the memory limit of its container is 8 Gi
