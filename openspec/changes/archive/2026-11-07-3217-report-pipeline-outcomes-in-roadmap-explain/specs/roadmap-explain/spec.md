## ADDED Requirements

### Requirement: Totals of the last implement run
The command SHALL report the token total, the seconds total, the repair-round count and the outcome counts of the last implement run of the item.

#### Scenario: Totals of a fixture run
- **WHEN** the job record of the fixture item holds a trace with one model event of 1200 input tokens, 300 output tokens and 90 seconds, and two attempt events, the first with outcome `failed` and next `repair`, the second with outcome `passed` and next `stop`
- **THEN** the output reports 1500 tokens, 90 seconds, 1 repair round, 1 failed outcome and 1 passed outcome

### Requirement: The JSON object gives the same totals
The command SHALL give the same totals as a JSON object when it runs with `--json`.

#### Scenario: The JSON object agrees with the text
- **WHEN** the command runs with `--json` on the fixture item
- **THEN** the JSON object holds `tokens_total` 1500, `seconds_total` 90, `repair_rounds` 1 and `outcomes` with 1 failed and 1 passed, and the text output holds the same values

### Requirement: Item with no recorded run
The command SHALL state that the item has no recorded implement run when the job record holds no trace, and SHALL give no totals.

#### Scenario: No trace in the record
- **WHEN** the job record of the fixture item holds no `implement.trace` value
- **THEN** the output states that the item has no recorded run and gives no totals, and the JSON object gives null for each total

### Requirement: Dropped events beside the totals
The command SHALL state the number of events that the trace bound dropped, beside the totals.

#### Scenario: Trace with dropped events
- **WHEN** the trace of the fixture item reports 12 dropped events
- **THEN** the output names 12 dropped events and says that the totals leave them out

## MODIFIED Requirements

### Requirement: The command makes no model call and no write
The command SHALL call no model, SHALL write nothing to GitHub or to git, and SHALL change no label, comment or record. It SHALL read the issues, the branches and the change folders that the plan of the job reads. With `--trace` it SHALL read the one issue. It SHALL report the totals from the job record of the issue that it reads.

#### Scenario: A read-only run
- **WHEN** `explain` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0 and the store records no write

#### Scenario: A read-only run of the trace
- **WHEN** `explain 7 --trace` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0, the store records no write, and it reads issue 7 once

#### Scenario: A run that reports totals
- **WHEN** `explain 7` runs on an item whose record holds a trace, with a model client that fails the test when it is built and a store that records writes
- **THEN** the output holds the totals and the store records no write
