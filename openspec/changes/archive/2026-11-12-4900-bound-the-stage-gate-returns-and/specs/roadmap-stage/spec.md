## ADDED Requirements

### Requirement: The returns of a refused reply have a hard ceiling and stop with the Service
The settings load SHALL refuse a value of `roadmap.stage.gate_returns` above `CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` (3), because each return is one more plan run. After the Service stops, the stage job SHALL start no return of a refused reply: the round SHALL end with `ServiceStoppingError` and SHALL record no failure for the item.

#### Scenario: A value over the ceiling
- **WHEN** `roadmap.stage.gate_returns` is 4
- **THEN** the settings load fails with an error that names `gate_returns`

#### Scenario: The Service stops during a plan
- **WHEN** the Service stops while the planner gives a reply that the checks refuse
- **THEN** the planner gets no return, the round ends with the stop, and the item has no refused-reply file
