## RENAMED Requirements

- FROM: `### Requirement: An item gets one extra return at most`
- TO: `### Requirement: An item gets the extra returns of its setting`

## MODIFIED Requirements

### Requirement: The limit of refused plans returns the item to New
The `plan_defect` failure that brings the count to `roadmap.stage.plan_defect_limit` (default 3) SHALL return the item to New in the same round. The job SHALL read the setting in each round. The job SHALL post one comment that lists in sequence, one line each and with no handle that pings, the problems of the refused replies of the last plan and then the reason of the failure, unless the checks refused the last reply. It SHALL then set New with the failure keys and clear both count keys.

#### Scenario: The third refused plan
- **WHEN** an item has 2 `plan_defect` failures on its body and a round of the Service refuses its plan again
- **THEN** the item is New, one comment of the stage job lists the problems of the refused replies, and the job record holds no `stage.plan_defects`

#### Scenario: A higher limit
- **WHEN** `roadmap.stage.plan_defect_limit` is 5 and an item gets its fourth `plan_defect` failure on its body
- **THEN** the item stays Ready with the count 4, and the fifth failure returns it to New with a comment that names 5

#### Scenario: A failure with no refused reply
- **WHEN** the failure at the limit holds no problem of a refused reply
- **THEN** the comment lists the reason of the failure

#### Scenario: A plan run that stops after a refused reply
- **WHEN** the checks refuse the first reply of the last plan and the second plan run stops
- **THEN** the comment lists the problem of the refused reply and then the reason of the stop

#### Scenario: A problem that names a handle
- **WHEN** a problem at the limit holds a handle and a line break
- **THEN** the comment shows the problem on one line with the handle in a code span

### Requirement: The returns of a refused reply have a hard ceiling and stop with the Service
The settings load SHALL refuse a value of `roadmap.stage.gate_returns` above 4 times its default, 12, because each return is one more plan run. After the Service stops, the stage job SHALL start no return of a refused reply: the round SHALL end with `ServiceStoppingError` and SHALL record no failure for the item.

#### Scenario: A value over the ceiling
- **WHEN** `roadmap.stage.gate_returns` is 13
- **THEN** the settings load fails with an error that names `gate_returns`

#### Scenario: A doubled value
- **WHEN** `roadmap.stage.gate_returns` is 6
- **THEN** the settings load gives 6

#### Scenario: The Service stops during a plan
- **WHEN** the Service stops while the planner gives a reply that the checks refuse
- **THEN** the planner gets no return, the round ends with the stop, and the item has no refused-reply file

### Requirement: An item gets the extra returns of its setting
An item SHALL get at most `roadmap.stage.gate_return_extensions` extra returns (default 1), so a reply SHALL get at most `roadmap.stage.gate_returns` + `roadmap.stage.gate_return_extensions` + 1 planner requests. The planner SHALL read the setting in each round. No extra return SHALL start after the Service stops.

#### Scenario: Each reply has a new finding
- **WHEN** each reply removes the finding of the reply before and has a new one
- **THEN** the planner gets `roadmap.stage.gate_returns` + 2 requests at the defaults, 1 + 3 + 2 requests when `roadmap.stage.gate_return_extensions` is 2, and the item fails

#### Scenario: The Service stops before the extra return
- **WHEN** the Service stops while the planner gives the reply that gets the extra return
- **THEN** the extra return does not start and the round ends with the stop
