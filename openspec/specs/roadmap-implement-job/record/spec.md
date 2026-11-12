# roadmap-implement-job/record Specification

## Purpose
The record of an implement run: the job record, the trace, the comment of each run, the spend and the token counts, and the metrics of the outcomes and the failures.

## Requirements

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

### Requirement: The job record keeps the base that a withdraw restores
The job SHALL write `implement.base` once, in the write that sets the Status In Progress, and keep an existing value. The value SHALL be the sha of `origin/<branch>` for a Staged item and `new` for a Planned item. The job SHALL clear `implement.base` when it marks the pull request ready and when it returns the item to New.

#### Scenario: The base of a Staged item and of a Planned item
- **WHEN** the job starts a Staged item and a Planned item
- **THEN** the record of the Staged item holds the sha of its branch on `origin`, and the record of the Planned item holds `new`

#### Scenario: The base is kept by a second Job and cleared at ready
- **WHEN** a first Job is killed after two groups, a second Job takes the item, and the second Job marks the pull request ready
- **THEN** the second Job sees the base of the first Job, and the record holds no `implement.base` after the ready mark

### Requirement: A dry run makes no request
`--dry-run` SHALL make no request, SHALL return the plan type marked as a dry run, and SHALL list the reads and the writes of a run in order.

#### Scenario: Dry run
- **WHEN** `devops roadmap implement --dry-run` runs
- **THEN** no git command runs, no GitHub request is made, and the output lists the requests of a run

### Requirement: The job keeps the trace of its run
The job SHALL clear `implement.trace` when a run starts, and SHALL write it with each record of a passed group, with a stop and with the ready mark. The value SHALL be JSON with the events and the count `dropped`. When the value is longer than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters, the job SHALL drop the oldest `model` events first, then the oldest other events, count them in `dropped`, and keep the sums of their tokens, seconds, repair rounds and outcomes.

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

### Requirement: The spend itemizes token cost per tier
The implement job SHALL itemize the spend of every step under the tier that served it in `implement.spend`.

#### Scenario: Spend itemized per tier
- **WHEN** two steps ran on tier `devops-coder` and tier `devops-reasoning`
- **THEN** the record of the spend holds the token count for each tier and the aggregate total

### Requirement: The report reads the item again
`_report` of the Service SHALL read the item again after it reads the log of the Job and before it decides whether the Job left a stop. A stop that the runner wrote in that time SHALL keep its class, and the Service SHALL write no second class.

#### Scenario: The runner stops while the report reads the log
- **WHEN** the item is In Progress in the listing of the round, and the runner writes its stop with the class `timeout` while the report reads the log of the Job
- **THEN** the record keeps the class `timeout`, the report names `timeout`, and the counter for `timeout` grows by 1

### Requirement: The metric labels are classes of the taxonomy
Each panel and alert rule of `k8s/` that reads `devops_cli_service_implement_failures_total` SHALL match the label `class` only with values of the taxonomy.

#### Scenario: A matcher with an unknown value
- **WHEN** a test reads the files of `k8s/` that name the metric
- **THEN** every value of a `class` matcher in them is a class of the taxonomy

### Requirement: The record keeps the size of the first request of each step
The implement job SHALL record in `implement.spend`, under `steps`, the input tokens of the first model request of each step, from the usage of the first reply of the step. The job SHALL write the figure apart from the trace, so the limit of the trace never drops it.

#### Scenario: A step records its first request
- **WHEN** a step makes two model requests
- **THEN** `implement.spend` holds for that step the input tokens of the first request, and they equal `tokens_in` of the first `model` event of the step.

#### Scenario: A trace over its limit keeps the figure
- **WHEN** a run has more events than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` allows
- **THEN** the trace has a `dropped` count above 0, and `implement.spend` still holds the first-request figure of each step.

### Requirement: Implement job outcome counter
The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class` and `result` once for each runner Job that a round reports. The `result` SHALL be `failed` when the report finds a failure class, and the state of the Job (`succeeded`, `failed` or `gone`) otherwise.

#### Scenario: A reported runner Job counts once
- **WHEN** A round reports a runner Job for repository `owner/repo` and item class `feat` that ended Complete with the result `ready`.
- **THEN** The series `devops_cli_service_implement_jobs_total{repo="owner/repo",item_class="feat",result="succeeded"}` increases by one.

#### Scenario: A stop that the runner wrote before it exited 0
- **WHEN** A round of `example/app` reports a runner Job that ended Complete, and its item holds the stop with the class `parser`.
- **THEN** The series with `result` `failed` increases by one, the series with `result` `succeeded` does not change, the failures counter for `parser` and `example/app` increases by one, and a second round adds nothing.

### Requirement: Repair rounds counter
The roadmap Service SHALL increment `devops_cli_service_implement_repair_rounds_total` with the labels `repo` and `item_class` by the repair-round count of each reported implement step.

#### Scenario: Repair rounds add to the counter
- **WHEN** A reported implement step records two repair rounds for repository `owner/repo` and item class `feat`.
- **THEN** The series `devops_cli_service_implement_repair_rounds_total{repo="owner/repo",item_class="feat"}` increases by two.

### Requirement: Token counter
The roadmap Service SHALL increment `devops_cli_service_implement_tokens_total` with the labels `repo` and `item_class` by the tokens that the reported runner Job spent, and not by the tokens of earlier Jobs of the item.

#### Scenario: Tokens add to the counter
- **WHEN** A reported runner Job for repository `owner/repo` and item class `feat` records 1,000 tokens.
- **THEN** The series `devops_cli_service_implement_tokens_total{repo="owner/repo",item_class="feat"}` increases by 1,000.

### Requirement: Counted spend
The job record holds the spend of all Jobs of the item, so the roadmap Service SHALL keep the counted token total in the job record key `implement.spend_counted`. It SHALL add only the difference between the spend and that total to the token counter, and SHALL write the new total in the same write that records the state of the Job.

#### Scenario: A second Job counts only its own tokens
- **WHEN** The record of an item holds 1,500 tokens when its first Job is reported, and 4,000 tokens (the sum of both Jobs) when its second Job is reported.
- **THEN** The series increases by 1,500 at the first report and by 2,500 at the second, and `implement.spend_counted` holds `1500` and then `4000`.

### Requirement: Counted spend edge cases
A spend below the counted total SHALL count whole once and become the counted total. A record with no `implement.spend_counted` SHALL count its whole spend once.

#### Scenario: A spend below the counted total counts whole
- **WHEN** The record holds 900 tokens in `implement.spend` and `1500` in `implement.spend_counted` when a Job is reported.
- **THEN** The series increases by 900 and `implement.spend_counted` holds `900`.

#### Scenario: A record of an older version counts its spend once
- **WHEN** The record holds 1,500 tokens in `implement.spend` and no `implement.spend_counted` when a Job is reported.
- **THEN** The series increases by 1,500 and `implement.spend_counted` holds `1500`.

#### Scenario: A Job that spent nothing adds nothing
- **WHEN** The record holds 1,500 tokens in both `implement.spend` and `implement.spend_counted` when a Job is reported.
- **THEN** The series does not increase.

### Requirement: Consecutive-failure gauge
The roadmap Service SHALL expose `devops_cli_service_implement_consecutive_failures` with the labels `repo` and `class`, and the gauge SHALL hold the number of stops in a row of that class.

#### Scenario: A stop increments its class gauge
- **WHEN** A reported stop has class `tests` and the gauge for `tests` is 1.
- **THEN** The gauge `devops_cli_service_implement_consecutive_failures{repo="owner/repo",class="tests"}` becomes 2.

### Requirement: Consecutive-failure gauge persists
The roadmap Service SHALL keep the consecutive-failure gauge value in a state record and SHALL report the same value after a restart.

#### Scenario: A restart keeps the gauge value
- **WHEN** A Service stops with `devops_cli_service_implement_consecutive_failures{repo="owner/repo",class="tests"}` at 2 and a new Service starts from the same state record.
- **THEN** The new Service exposes the same gauge value 2.

### Requirement: Different class resets the earlier gauge
The roadmap Service SHALL set the consecutive-failure gauge of a class to zero when a stop of another class follows.

#### Scenario: A different class resets the earlier gauge
- **WHEN** The gauge for class `tests` is 2 and the next reported stop has class `timeout`.
- **THEN** The gauge for `tests` becomes 0 and the gauge for `timeout` becomes 1.

### Requirement: Delivered item resets the earlier gauge
The roadmap Service SHALL set the consecutive-failure gauge of a class to zero when a delivered item follows.

#### Scenario: A delivered item resets the earlier gauge
- **WHEN** The gauge for class `tests` is 2 and a runner Job reports a delivered item.
- **THEN** The gauge for `tests` becomes 0.

### Requirement: Repair rounds in the job record
The roadmap Service SHALL record the integer repair-round count of each implement step in the item job record from `StepOutcome.repair_rounds`.

#### Scenario: A step with repair rounds is recorded
- **WHEN** An implement step ends with two repair rounds.
- **THEN** The item job record holds the integer `2` for the step's repair-round count.

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

### Requirement: A retry and a return to New clear the counted spend
The job SHALL clear `implement.spend_counted` in the same write that clears `implement.spend`, at the start of a retry and at a return to New.

#### Scenario: A retry starts the count from zero
- **WHEN** A person retries an item whose record holds `implement.spend_counted`, and the new Job starts.
- **THEN** the record holds no `implement.spend_counted`.

#### Scenario: A return to New clears the count
- **WHEN** The job returns an item to New and its record holds `implement.spend_counted`.
- **THEN** the record holds no `implement.spend_counted`.

### Requirement: The comments and the record show the extension of a step budget
The record `implement.spend` SHALL hold, for each step that got the one extension of its token budget, the old budget, the new budget, the counts that gave it and whether the ceiling cut it. The ready comment and the stop comment of the item SHALL list each such step of the run, the earlier Jobs included, with the budgets and the counts only. A run with no extension SHALL show no such list.

#### Scenario: A ready item with an extended step
- **WHEN** group 1 got an extension from 100 to 150 input tokens with 2 successful edits and 0 refused commands, and the item reaches a ready pull request
- **THEN** the ready comment lists group 1 with 100 to 150 input tokens and those counts, and the record holds the extension of group 1 and none for group 2

#### Scenario: A stop after an extension
- **WHEN** group 1 got an extension and then reached its new budget
- **THEN** the stop comment names the class `limit_reached`, lists the extension of group 1 and gives the reason that names the extension

#### Scenario: No extension
- **WHEN** no step of the run got an extension
- **THEN** the comment of the item lists no budget extension

### Requirement: The record keeps the tokens of each step
The implement job SHALL record in `implement.spend`, under `steps`, for each step: its model requests, its input tokens, its output tokens, its repair rounds and the input tokens of its largest model request, from the usage of the replies of the step. The job SHALL write these figures apart from the trace, so the limit of the trace never drops them.

#### Scenario: A step whose requests grow
- **WHEN** the requests of a step report an input that grows with the conversation
- **THEN** the entry of the step holds the count of the `model` events of the step, the sums of their `tokens_in` and `tokens_out`, and their largest `tokens_in`, which is above the first request of the step

#### Scenario: A step with a repair round
- **WHEN** the lint check of group 1 fails once and one repair turn fixes it
- **THEN** the entry of group 1 holds 1 repair round and the 4 requests of both turns
