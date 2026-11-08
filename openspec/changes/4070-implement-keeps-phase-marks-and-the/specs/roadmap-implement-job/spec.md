## MODIFIED Requirements

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.base`, `implement.checked_sha`, `implement.published_sha`, `implement.stopped`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step that the Jobs of the item ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a ready pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a ready pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

## ADDED Requirements

### Requirement: The job skips a phase that passed at the same head
The job SHALL write `implement.checked_sha` with the head after the scoped checks pass, and `implement.published_sha` with the head after it pushes the item branch. A job whose head equals `implement.checked_sha` SHALL run no scoped check. A job whose head equals `implement.published_sha` SHALL push nothing. The job SHALL clear both keys when it marks the pull request ready and when it returns the item to New.

#### Scenario: A second Job at a checked head
- **WHEN** a first Job passes the scoped checks, pushes, and stops in the watch of the checks, and a second Job starts at the same head
- **THEN** the second Job runs no scoped check and pushes nothing, and the record holds both keys until the pull request is ready

#### Scenario: A head that moved
- **WHEN** `implement.checked_sha` holds a sha that is not the head
- **THEN** the job runs the scoped checks and writes the new head

### Requirement: The comment of a run carries the marker of the run
The comment of the job on the pull request SHALL start with the marker of the implement job, and its second line SHALL be `<!-- devops roadmap implement run: <job> -->`, where `<job>` is the value of `implement.job`, or `manual` when the record holds none.

#### Scenario: The marker of a runner Job
- **WHEN** the record holds `implement.job` and the job posts its comment
- **THEN** the first line is the marker of the implement job and the second line names the run

#### Scenario: A job with no job record
- **WHEN** the record holds no `implement.job`
- **THEN** the second line of the comment names the run `manual`

### Requirement: The job keeps one comment for each run
The job SHALL read the comments of the pull request once. It SHALL post one comment for its run, and update that comment for each later write, with the table of all steps of the job. It SHALL write no comment when it has no step, amendment, scoped run or skipped step to show. No comment SHALL have the body `-`.

#### Scenario: A repair round
- **WHEN** a check fails, a fix step runs and the check passes
- **THEN** the pull request holds one comment with the marker of the run, updated once, with the rows of the groups and of the fix

#### Scenario: A rerun with no new outcome
- **WHEN** a second Job finds every group ticked and runs no step
- **THEN** the job posts no comment, and the comment of the first Job keeps its table

### Requirement: The spend of a killed Job counts toward the item budget
The job SHALL write `implement.spend` with each passed group. At the start, the job SHALL read the recorded spend and add it to the spend of its own steps, for the item budget and for the spend that a stop or ready writes. A retry that a person asks for SHALL start from zero spend. A return to New SHALL clear `implement.spend`.

#### Scenario: A continuation after a kill
- **WHEN** a Job is killed after group 1 spent 100 input tokens, and the item budget is 150
- **THEN** the second Job stops with the class `limit_reached` after its first request, and the record of a finished item holds the requests and tokens of both Jobs

#### Scenario: A retry of a person
- **WHEN** a person retries a stopped item
- **THEN** the Job starts from zero spend

#### Scenario: A record of an older version
- **WHEN** the record holds `implement.spend` as an earlier version wrote it, and none of the phase marks
- **THEN** the job starts from that spend and runs the scoped checks

### Requirement: The watch of the checks writes a progress line
While the checks of the pull request run, the job SHALL write one log line at each poll after the first: `The checks of pull request #<pull> still run after <seconds> s.`. The poll interval SHALL be the interval of the watch.

#### Scenario: A watch of three intervals
- **WHEN** a check runs for 60 seconds with a poll interval of 30 seconds
- **THEN** the log holds the lines for 30 s and 60 s, and no line when the checks settle at the first poll

### Requirement: The comment and the phase marks cost five requests
A job SHALL send at most 5 requests more than before for the comment and the phase marks: one read of the comments of the pull request, and for each of the two phase marks one read and one write of the item. A repair round SHALL NOT read the comments again.

#### Scenario: A Job that writes both phase marks
- **WHEN** a job takes an item to a ready pull request
- **THEN** it reads the comments once and writes each phase mark once
