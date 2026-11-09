## MODIFIED Requirements

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.base`, `implement.checked_sha`, `implement.published_sha`, `implement.stopped`, `implement.result`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step that the Jobs of the item ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a ready pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a ready pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

#### Scenario: A record of an older version
- **WHEN** the record of an item holds no `implement.result`
- **THEN** the record loads with the key absent and every other key unchanged

### Requirement: A Job that leaves its item eligible stops the item
When a reported Job leaves its item neither In Review nor stopped, and the record holds no `implement.result` of `ready`, `yielded` or `returned`, the round SHALL set the item Blocked and record `implement.stopped` as `job`. No Job SHALL be created for the item before a clear rule runs.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed, the item is In Progress, the record holds no `implement.result`, and no continuation applies to it
- **THEN** the item gets a comment with the state `failed` and the tail of the log
- **AND** `implement.job_state` is `failed`, the Status is Blocked, and `implement.stopped` is `job`
- **AND** the next round creates no Job for the item

### Requirement: A stop names the failed check and the end of its log
A stop of a fix step, and a stop of the scoped checks, SHALL name the failed check and hold the end of its log, at most `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters, with secrets masked. The stop comment and the job record (`implement.check`, `implement.check_log`) SHALL hold both. A retry or a clear rule of the Service SHALL remove `implement.check` with the stop, and the next Job SHALL remove `implement.check_log` in its first record write. The table of the comment SHALL show the check name as the last failing command when no command failed.

#### Scenario: A fix step that stops
- **WHEN** the check `Tests & Coverage` of the pull request fails with a log that holds a token, and the fix step changes no file
- **THEN** the comment names `Tests & Coverage`, holds the end of the log with the token masked, the row `fix` of the table shows the check name, and `implement.check` and `implement.check_log` hold the same

#### Scenario: A scoped check that still fails
- **WHEN** the scoped check `pre-push` fails after the last fix round
- **THEN** the comment and the record hold the name `pre-push` and the end of its log

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` and the job takes the item
- **THEN** `implement.check` and `implement.check_log` are removed

#### Scenario: A clear rule keeps the log
- **WHEN** a clear rule of the Service removes the stop of an item
- **THEN** `implement.check` is removed and `implement.check_log` stays

### Requirement: A conflict stop names the conflicted files
When a rebase stops the item on a conflict, the job SHALL read the unmerged files with `git diff --name-only --diff-filter=U` before it aborts the rebase. The stop comment SHALL name each file, the job record SHALL hold the files as `implement.conflict`, and the next Job SHALL clear the record in its first record write. A clear rule of the Service SHALL keep the record. The job SHALL mask each path, SHALL list at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths, and SHALL state the number of paths that the cut left out.

#### Scenario: A conflict at the start of a run
- **WHEN** the staged branch conflicts with the default branch in a real git repository when the job rebases at the start of the run
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: A conflict before the push
- **WHEN** the default branch gains a change that conflicts with the branch when the job rebases before the push
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: The record holds the files until a retry
- **WHEN** a conflict stops the item, and a person then comments `implement: retry`
- **THEN** `implement.conflict` holds each file after the stop, and holds none after the first record write of the next Job

#### Scenario: A clear rule keeps the files
- **WHEN** a conflict stops the item and a clear rule of the Service removes the stop
- **THEN** `implement.conflict` still holds each file

#### Scenario: A list above the limit
- **WHEN** the conflict holds more files than `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
- **THEN** the comment names the files up to the limit and states the number of files left out

#### Scenario: A secret in a path
- **WHEN** a conflicted file path holds a token that `mask_secrets` knows
- **THEN** the comment and the record hold the masked path and not the token

## ADDED Requirements

### Requirement: The job writes how its run ended
The job SHALL write `implement.result` as the last mark of the write that ends each run of an item. The value SHALL be `ready` for a pull request marked ready, `stopped` for a stop, `yielded` for a claim, and `returned` for a return to New. The job SHALL clear the key in its first record write of a run.

#### Scenario: A run that a claim ended
- **WHEN** a person claims the item while group 1 runs
- **THEN** the record holds `implement.result` equal to `yielded`

#### Scenario: A run that stops
- **WHEN** the scoped checks stop the item
- **THEN** the record holds `implement.result` equal to `stopped`, written after `implement.stopped`

#### Scenario: A stale result
- **WHEN** a new Job starts on an item whose record holds `implement.result` equal to `ready`, and the Job is killed in its first group
- **THEN** the record holds no `implement.result`

### Requirement: The Service clears the result when it records a Job
The Service SHALL clear `implement.result` in the write that records a new Job of an item.

#### Scenario: A Job that dies before its first write
- **WHEN** the record of an item holds `implement.result` equal to `yielded` and a round creates a Job for the item
- **THEN** the record holds `implement.job` and no `implement.result`

### Requirement: The report reads the result of a Job
The round SHALL read `implement.result` when it reports a Job that ended. A Job with the result `ready`, `yielded` or `returned` SHALL cause no stop of the item. A Job with no result SHALL get its stop and its class from the Status of the item and the tail of its log, with `classify_failure`.

#### Scenario: A yielded Job
- **WHEN** the Job of an item ended, the item is In Progress, and the record holds `implement.result` equal to `yielded`
- **THEN** the round records `implement.job_state`, sets no Status, and records no `implement.stopped`

#### Scenario: A Job with no result
- **WHEN** the Job of an item failed, the item is In Progress, the record holds no result, and the log holds an out-of-memory line
- **THEN** the round records the class `oom` and sets the item Blocked

### Requirement: The first step of a run gets the stop of the earlier Job
The job SHALL read `implement.check_log` and `implement.conflict` before its first record write of a run. It SHALL give both to the first step of the run in a section `# The stop of the earlier Job` of the step message, and to no later step. The section SHALL be left out when both are empty. The prompt `roadmap_implement_step.md` SHALL state what the section holds.

#### Scenario: A retry after a failed check
- **WHEN** an item stopped with a recorded check log and recorded conflict files, and a trusted person retries
- **THEN** the message of the first step holds the log and the files, the message of the second step holds neither, and the record holds neither key after the first record write

#### Scenario: A continuation after a clear rule
- **WHEN** a clear rule of the Service removed the stop and a new Job takes the item
- **THEN** the message of the first step holds the recorded log
