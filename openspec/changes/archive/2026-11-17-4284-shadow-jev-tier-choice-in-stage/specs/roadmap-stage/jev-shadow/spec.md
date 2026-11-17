## ADDED Requirements

### Requirement: Switch off makes no Jev call
The stage job SHALL make no Jev call when `roadmap.stage.jev_shadow` is off.

#### Scenario: Switch off
- **WHEN** a stage round plans an item with `roadmap.stage.jev_shadow` off and a fake Jev that records its calls
- **THEN** the fake Jev records zero calls, and no log line and no counter sample for the metric exist

### Requirement: Switch on logs and counts the choice
The stage job SHALL log one line for each item and SHALL increment `devops_cli_roadmap_stage_jev_total` once with the label `choice` before the first plan call, when `roadmap.stage.jev_shadow` is on.

#### Scenario: Switch on
- **WHEN** a stage round plans an item with the switch on and a fake Jev that picks the sonnet tier
- **THEN** one log line holds the item, the choice, the complexity, `high_risk` and the concrete-files probability, and the counter with `choice=sonnet` is 1

### Requirement: Shadow mode changes nothing
The stage job SHALL produce the same plan result, the same model and the same item list with the switch on as with the switch off.

#### Scenario: Result equals the run with the switch off
- **WHEN** the same fake items run twice, once with the switch off and once with the switch on
- **THEN** the plan result, the model name of each plan call and the item list are equal in both runs, and no comment is added

### Requirement: Jev error does not stop the item
The stage job MUST log a Jev error, MUST count it with `choice=error` and MUST continue to plan the item as before.

#### Scenario: Jev raises an error
- **WHEN** the fake Jev raises an exception and the switch is on
- **THEN** the counter with `choice=error` is 1, the log holds the error, and the item is planned with the same result as with the switch off

### Requirement: Metric has three series
The metric `devops_cli_roadmap_stage_jev_total` SHALL have the single label `choice` with only the values `deepseek`, `sonnet` and `error`, and the generated metric table SHALL state 3 series.

#### Scenario: Docs sync
- **WHEN** `uv run devops docs generate` runs
- **THEN** the metric table of `docs/TELEMETRY.md` lists the metric with 3 series, and the docs check passes

### Requirement: Test module runs offline
The test module `tests/roadmap/stage/test_stage_jev_shadow.py` SHALL pass with `uv run devops ci test` and SHALL make no network call.

#### Scenario: Offline run
- **WHEN** the test module runs with a fake Jev and no network
- **THEN** all tests pass, and the module fails before the change because it does not exist
