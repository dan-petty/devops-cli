## ADDED Requirements

### Requirement: A refused reply that makes progress gets one extra return
When the checks refuse a reply at the last return of `roadmap.stage.gate_returns`, the stage job SHALL give the reply one more return only when no finding of the reply before it stays (the same gate and the same text, with the digits masked) and no finding of the reply has the fix class `never` in `stage_finding_classes.json`. The rule SHALL make no model call.

#### Scenario: The findings fall as in item 5136
- **WHEN** the replies have 3 findings, then 1 of them two times, then 1 new finding, and the reply of the extra return passes the checks
- **THEN** the planner gets 5 requests and the item stages

#### Scenario: A finding stays
- **WHEN** each reply has the same finding of the gate `paths`
- **THEN** the planner gets 1 + `roadmap.stage.gate_returns` requests and the item fails

#### Scenario: A finding of a code that no return fixed
- **WHEN** the last reply has a new `stage_problem_missing_test_file` finding and no finding of the reply before
- **THEN** the reply gets no extra return

### Requirement: An item gets one extra return at most
An item SHALL get at most `CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS` extra returns, so a reply SHALL get at most `roadmap.stage.gate_returns` + 2 planner requests. No extra return SHALL start after the Service stops.

#### Scenario: Each reply has a new finding
- **WHEN** each reply removes the finding of the reply before and has a new one
- **THEN** the planner gets `roadmap.stage.gate_returns` + 2 requests and the item fails

#### Scenario: The Service stops before the extra return
- **WHEN** the Service stops while the planner gives the reply that gets the extra return
- **THEN** the extra return does not start and the round ends with the stop

### Requirement: Each extension decision and its end are logged and counted
Each decision at the last return SHALL log one `stage gate extension:` line with its counts and its result, and in a run of a repository SHALL add 1 to `devops_cli_roadmap_stage_gate_extension_total` by `result`: `extended`, `used`, `first`, `stuck` or `never`. Each extra return SHALL log one `stage gate extension end:` line with the result `passed`, `refused` or `ended`, and in a run of a repository SHALL add 1 to `devops_cli_roadmap_stage_gate_extension_ends_total` by `result`.

#### Scenario: The extra return passes
- **WHEN** the replies fall as in item 5136 and the reply of the extra return passes the checks
- **THEN** the job logs one `stage gate extension:` line with `returns=3 in=1 gone=1 stuck=0 new=1 never=0 result=extended`, one `stage gate extension end:` line with `returns=4 result=passed`, and one count of each counter

#### Scenario: The second decision of an item
- **WHEN** each reply removes the finding of the reply before and has a new one
- **THEN** the decisions have the results `extended` and `used`, and the end line has `result=refused`

#### Scenario: The run ends before the checks judge the extra reply
- **WHEN** the Service stops while the planner gives the reply that gets the extra return
- **THEN** the end line has `result=ended`

### Requirement: The failure of a refused reply names the stop
The failure of a reply that the checks refuse after its last return SHALL name the number of the return and the stop of the extension, with the gates of the findings that stopped it.

#### Scenario: A finding stays
- **WHEN** each reply has the same finding of the gate `paths`
- **THEN** the failure text says that a finding of the gate `paths` stays from the reply before

#### Scenario: The item used its extra return
- **WHEN** each reply removes the finding of the reply before and has a new one
- **THEN** the failure text says that the item used its extra return
