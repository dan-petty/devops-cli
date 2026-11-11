## MODIFIED Requirements

### Requirement: Totals of the last implement run
The command SHALL report the token total, the seconds total, the repair-round count and the outcome counts of the last implement run of the item. The totals SHALL include the model events and the attempt events that the trace bound dropped.

#### Scenario: Totals of a fixture run
- **WHEN** the job record of the fixture item holds a trace with one model event of 1200 input tokens, 300 output tokens and 90 seconds, and two attempt events, the first with outcome `failed` and next `repair`, the second with outcome `passed` and next `stop`
- **THEN** the output reports 1500 tokens, 90 seconds, 1 repair round, 1 failed outcome and 1 passed outcome

#### Scenario: A long run
- **WHEN** the trace of the item holds 100 model events of 20,000 input tokens, 300 output tokens and 4 seconds each, 150 shell calls and a failed attempt, and the bound drops every model event
- **THEN** the output reports 2030000 tokens and 400.0 seconds, the totals of the full run, and `--json` gives the same values

#### Scenario: A trace with no dropped sums
- **WHEN** the trace holds `events` and `dropped` and no dropped sum, as a trace from before the sums
- **THEN** the trace decodes with no error, and the totals are the sums of the kept events

### Requirement: Dropped events beside the totals
The command SHALL state the number of events that the trace bound dropped, beside the totals, and SHALL say that the totals include them.

#### Scenario: Trace with dropped events
- **WHEN** the trace of the fixture item reports 12 dropped events
- **THEN** the output names 12 dropped events and says that the totals include them
