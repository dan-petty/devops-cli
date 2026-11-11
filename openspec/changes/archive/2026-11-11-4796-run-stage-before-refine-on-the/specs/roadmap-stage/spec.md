## MODIFIED Requirements

### Requirement: The Service runs the stage job on the model lane
The model lane SHALL hold the row `stage` after `retitle` and before `refine`. The row SHALL be due every 37 minutes, on its first run, and when a `stage_due` stamp is at or after its last success. A round in which `refine` set an item Ready SHALL write that stamp. The row SHALL run the stage job in the model clone and fail the round only when it tried items and staged or stopped none, or for a failure that no item explains. The dry run SHALL list the row when it is due.

#### Scenario: The first run
- **WHEN** a repository has no record of a `stage` round
- **THEN** the row is due, after the rows that come before it

#### Scenario: The interval
- **WHEN** the last success of the row is 37 minutes old and no other trigger exists
- **THEN** the row is due
- **AND** with a last success 36 minutes old, the row is not due

#### Scenario: Stage runs before refine
- **WHEN** the rows `stage` and `refine` are both due in a round
- **THEN** the round runs `stage` before `refine`

#### Scenario: Refine set an item Ready
- **WHEN** the row succeeded in a round and the `refine` row of the same round set an item Ready
- **THEN** the round writes `stage_due` to `schedule.json`, and a round 5 minutes later runs the row

#### Scenario: Refine set an item Ready and failed another
- **WHEN** the `refine` row of a round set one item Ready and failed for another item
- **THEN** the round writes `stage_due` to `schedule.json`, and the row is due in a round 5 minutes later
- **AND** the round still fails for the `refine` row

#### Scenario: Refine set no item Ready
- **WHEN** the row succeeded in a round and the `refine` row of the same round set no item Ready
- **THEN** a round 5 minutes later does not run the row

#### Scenario: The dry run
- **WHEN** `devops roadmap run --dry-run` runs for a repository with no record of a round
- **THEN** its `Due:` line lists `stage` before `refine`, and no request is made
