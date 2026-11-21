## ADDED Requirements

### Requirement: The job record keeps the base until the run ends
The job SHALL write `implement.base` once, in the write that sets the Status In Progress, and keep an existing value. The value SHALL be the sha of `origin/<branch>` for a Staged item and `new` for a Planned item. The job SHALL clear `implement.base` when the run ends at the draft and when it returns the item to New.

#### Scenario: The base of a Staged item and of a Planned item
- **WHEN** the job starts a Staged item and a Planned item
- **THEN** the record of the Staged item holds the sha of its branch on `origin`, and the record of the Planned item holds `new`

#### Scenario: The base is kept by a second Job and cleared at the end
- **WHEN** a first Job is killed after two groups, a second Job takes the item, and the run of the second Job ends at the draft
- **THEN** the second Job sees the base of the first Job, and the record holds no `implement.base` after the end

### Requirement: The end comment, the stop comment and the record show the extension of a step budget
The record `implement.spend` SHALL hold, for each step that got the one extension of its token budget, the old budget, the new budget, the counts that gave it and whether the ceiling cut it. The end comment and the stop comment of the item SHALL list each such step of the run, the earlier Jobs included, with the budgets and the counts only. A run with no extension SHALL show no such list.

#### Scenario: A drafted item with an extended step
- **WHEN** group 1 got an extension from 100 to 150 input tokens with 2 successful edits and 0 refused commands, and the item reaches a draft pull request
- **THEN** the end comment lists group 1 with 100 to 150 input tokens and those counts, and the record holds the extension of group 1 and none for group 2

#### Scenario: A stop after an extension
- **WHEN** group 1 got an extension and then reached its new budget
- **THEN** the stop comment names the class `limit_reached`, lists the extension of group 1 and gives the reason that names the extension

#### Scenario: No extension
- **WHEN** no step of the run got an extension
- **THEN** the comment of the item lists no budget extension

## MODIFIED Requirements

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.base`, `implement.checked_sha`, `implement.published_sha`, `implement.stopped`, `implement.result`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step that the Jobs of the item ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a draft pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a draft pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

#### Scenario: A record of an older version
- **WHEN** the record of an item holds no `implement.result`
- **THEN** the record loads with the key absent and every other key unchanged

### Requirement: The job keeps the trace of its run
The job SHALL clear `implement.trace` when a run starts, and SHALL write it with each record of a passed group, with a stop and with the end of the run at the draft. The value SHALL be JSON with the events and the count `dropped`. When the value is longer than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters, the job SHALL drop the oldest `model` events first, then the oldest other events, count them in `dropped`, and keep the sums of their tokens, seconds, repair rounds and outcomes.

#### Scenario: A trace that is too long
- **WHEN** a run makes more events than fit in `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters
- **THEN** the value is not longer than the bound, it holds the kept events whole in the order of the run, and `dropped` counts the others

#### Scenario: Many model events and few progress events
- **WHEN** a run records 5 `tool` or `check` events first, then 200 `model` events and an `attempt` event, and the encoded value is longer than the bound
- **THEN** the value holds the 5 `tool` or `check` events, the newest `model` events and the `attempt` event, and `dropped` counts only the dropped `model` events

#### Scenario: Progress events that alone do not fit
- **WHEN** the trace holds 100 `model` events and 10 `tool` events, and only 8 `tool` events fit the bound
- **THEN** the value holds the newest 8 `tool` events and no `model` event, and `dropped` is 102

#### Scenario: A stored trace from before the order of the run
- **WHEN** a stored trace holds its `model` events after the `tool` events of a turn
- **THEN** the trace decodes with no error, and its events keep the stored order

#### Scenario: A new run
- **WHEN** a person retries a stopped item
- **THEN** the job clears `implement.trace` before its first step, and the record holds only the events of the new run

#### Scenario: A Job that ends after a group
- **WHEN** the Service ends a Job after the record of group 1 and before the stop
- **THEN** the record holds the events of group 1

#### Scenario: The sums of dropped events
- **WHEN** the bound drops model events of 2,030,000 tokens and 400 seconds in all, and no attempt event
- **THEN** the value holds `dropped_tokens` 2030000 and `dropped_seconds` 400.0 and no dropped attempt sum, and a value that is decoded and written again holds the same sums

### Requirement: Implement job outcome counter
The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class` and `result` once for each runner Job that a round reports. The `result` SHALL be `failed` when the report finds a failure class, and the state of the Job (`succeeded`, `failed` or `gone`) otherwise.

#### Scenario: A reported runner Job counts once
- **WHEN** A round reports a runner Job for repository `owner/repo` and item class `feat` that ended Complete with the result `drafted`.
- **THEN** The series `devops_cli_service_implement_jobs_total{repo="owner/repo",item_class="feat",result="succeeded"}` increases by one.

#### Scenario: A stop that the runner wrote before it exited 0
- **WHEN** A round of `example/app` reports a runner Job that ended Complete, and its item holds the stop with the class `parser`.
- **THEN** The series with `result` `failed` increases by one, the series with `result` `succeeded` does not change, the failures counter for `parser` and `example/app` increases by one, and a second round adds nothing.

### Requirement: The comment and the phase marks cost five requests
A job SHALL send at most 5 requests more than before for the comment and the phase marks: one read of the comments of the pull request, and for each of the two phase marks one read and one write of the item. A repair round SHALL NOT read the comments again.

#### Scenario: A Job that writes both phase marks
- **WHEN** a job takes an item to a draft pull request
- **THEN** it reads the comments once and writes each phase mark once

### Requirement: The spend of a killed Job counts toward the item budget
The job SHALL write `implement.spend` with each passed group. At the start, the job SHALL read the recorded spend and add it to the spend of its own steps, for the item budget and for the spend that a stop or the end of a drafted run writes. A retry that a person asks for SHALL start from zero spend. A return to New SHALL clear `implement.spend`.

#### Scenario: A continuation after a kill
- **WHEN** a Job is killed after group 1 spent 100 input tokens, and the item budget is 150
- **THEN** the second Job stops with the class `limit_reached` after its first request, and the record of a finished item holds the requests and tokens of both Jobs

#### Scenario: A retry of a person
- **WHEN** a person retries a stopped item
- **THEN** the Job starts from zero spend

#### Scenario: A record of an older version
- **WHEN** the record holds `implement.spend` as an earlier version wrote it, and none of the phase marks
- **THEN** the job starts from that spend and runs the scoped checks

## REMOVED Requirements

### Requirement: The job record keeps the base that a withdraw restores
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The requirement "The job record keeps the base until the run ends" holds the rule.

### Requirement: The watch of the checks writes a progress line
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: None: the job runs no watch.

### Requirement: The comments and the record show the extension of a step budget
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The requirement "The end comment, the stop comment and the record show the extension of a step budget" holds the rule.

### Requirement: Kept work counts its outcome
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: `devops_cli_service_implement_jobs_total` and the result line count each runner Job; no counter replaces `devops_cli_service_kept_work_total`.
