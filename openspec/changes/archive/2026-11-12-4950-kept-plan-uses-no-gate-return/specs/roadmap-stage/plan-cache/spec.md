## ADDED Requirements

### Requirement: A refused kept plan uses no gate return
When the gates refuse a kept plan on the current staged commit, the stage job SHALL NOT count the refusal against `roadmap.stage.gate_returns`. The planner SHALL get a new first reply with the kept plan and its problem, and that reply SHALL have all the returns of `roadmap.stage.gate_returns`. The `stage gate returns` line SHALL count only the returns after that reply.

#### Scenario: Every reply stays refused
- **WHEN** the gates refuse the kept plan of item 1 and each reply of the planner
- **THEN** the planner gets 1 + `roadmap.stage.gate_returns` requests, the item fails, and the `stage gate returns` line holds `returns=` the value of `roadmap.stage.gate_returns`

#### Scenario: The new first reply passes
- **WHEN** the gates refuse the kept plan of item 1 and the next reply of the planner passes
- **THEN** the planner gets one request that holds the kept plan as `previous` and its problem, the item is ready, and the log holds no `stage gate returns` line

### Requirement: No new first reply starts after the Service stops
After the Service stops, the stage job SHALL NOT ask the planner for the new first reply of a refused kept plan. The round SHALL end with `ServiceStoppingError` and SHALL record no failure for the item.

#### Scenario: The Service stops before the new first reply
- **WHEN** the Service stops while the gates refuse the kept plan of item 1
- **THEN** the planner gets no request, the round ends with the stop, and the item has no refused-reply file
