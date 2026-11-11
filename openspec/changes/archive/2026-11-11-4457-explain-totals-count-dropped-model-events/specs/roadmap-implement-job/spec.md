## MODIFIED Requirements

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
