## ADDED Requirements

### Requirement: No new work starts once the Service stops
When the Service stops, no worker SHALL start a round, no round SHALL start a row, and the stage and refine rows SHALL start no next item. A row that the stop keeps from its start SHALL count no job and no failed round, and SHALL stay due.

#### Scenario: A round in flight at the stop
- **WHEN** the Service stops while a round runs and a trigger is pending
- **THEN** the round runs to its end, reads that the Service stops, and no round starts for the pending trigger

#### Scenario: A row after the stop
- **WHEN** the Service stops during the first row of a round
- **THEN** the next due row does not start, the round ends with the stop error, that row counts no job, and the next round runs it

#### Scenario: A stage item after the stop
- **WHEN** the Service stops while the stage job plans the first of three items
- **THEN** the first item gets its draft pull request, no other item is planned, and no item holds a failure

#### Scenario: A refine item after the stop
- **WHEN** the Service stops while the refine job refines the first of three items
- **THEN** the first item is written, the round ends with the stop error, and the next round takes the other two items

### Requirement: A stop of the Service drains in two bounded phases
The rounds in flight SHALL get `CONST_SERVICE_STOP_DRAIN_SECONDS` to end. Then the request budget SHALL refuse every GitHub request with the stop error, also one the window has room for, and the rounds still in flight SHALL get `CONST_SERVICE_STOP_CUT_SECONDS` to end. The grace period of the Service pod SHALL be `CONST_SERVICE_STOP_GRACE_SECONDS`, more than the sum of the two waits, and the pod SHALL have no preStop hook.

#### Scenario: A cut budget
- **WHEN** the budget is cut and its window has room
- **THEN** a request fails with the stop error

#### Scenario: A round past the drain wait
- **WHEN** a round still runs at the end of the drain wait and sends a GitHub request
- **THEN** the request fails with the stop error, the round counts as `stopped`, and the Service logs that the drain wait is over

#### Scenario: The grace period of the pod
- **WHEN** the manifest of the Service pod is read
- **THEN** its grace period is `CONST_SERVICE_STOP_GRACE_SECONDS`, more than the two waits together, and its container has no lifecycle hook
