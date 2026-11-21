## ADDED Requirements

### Requirement: Prepare clears the marks of the run before
`prepare` SHALL clear the marks of the run before: `implement.trace`, `implement.result`, `implement.published_sha` and `implement.repair_rounds`.

#### Scenario: The repair rounds of the Job before
- **WHEN** the record holds 3 repair rounds of the Job before, and a new Job starts
- **THEN** `prepare` clears `implement.repair_rounds`

## RENAMED Requirements

- FROM: `### Requirement: The spend of a killed Job counts toward the item budget`
- TO: `### Requirement: The spend of an earlier Job counts toward the item budget`

## MODIFIED Requirements

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch`, `implement.pr`, `implement.base`, `implement.plan_summary`, `implement.checked_sha`, `implement.published_sha`, `implement.stopped`, `implement.result`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL count every step of every Job of the item that reached `publish`. `publish` SHALL write the record when the run ends (#3702).

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
`prepare` SHALL clear `implement.trace` when a run starts, and `publish` SHALL write it once, when the run ends, so the record holds no trace of a Job that runs. The value SHALL be JSON with the events and the count `dropped`. When the value is longer than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters, the job SHALL drop the oldest `model` events first, then the oldest other events, count them in `dropped`, and keep the sums of their tokens, seconds, repair rounds and outcomes.

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
- **WHEN** the Service ends a Job after group 1 passed and before `publish`
- **THEN** the record holds no trace and no spend of the Job, and the next Job runs group 1 again

#### Scenario: The sums of dropped events
- **WHEN** the bound drops model events of 2,030,000 tokens and 400 seconds in all, and no attempt event
- **THEN** the value holds `dropped_tokens` 2030000 and `dropped_seconds` 400.0 and no dropped attempt sum, and a value that is decoded and written again holds the same sums

### Requirement: The spend of an earlier Job counts toward the item budget
`publish` SHALL write `implement.spend` once, when the run ends. At the start, the job SHALL read the recorded spend and add it to the spend of its own steps, for the item budget and for the spend that a stop, a return or the end of a drafted run writes. A Job that ends before `publish` SHALL write no spend, so the next Job starts from the spend of the last Job that reached `publish`. A retry that a person asks for SHALL start from zero spend. A return to New SHALL clear `implement.spend`.

#### Scenario: A continuation after a kill
- **WHEN** the Jobs that reached `publish` recorded a spend of 226 new tokens, the item budget is 300, and the Job after them is killed after group 1 and before `publish`
- **THEN** the record holds the spend of 226 new tokens, the next Job stops with the class `limit_reached` after its first request, and the record of a finished item holds the requests and tokens of each Job that reached `publish`

#### Scenario: A retry of a person
- **WHEN** a person retries a stopped item
- **THEN** the Job starts from zero spend

#### Scenario: A record of an older version
- **WHEN** the record holds `implement.spend` as an earlier version wrote it, and none of the phase marks
- **THEN** the job starts from that spend and runs the scoped checks
