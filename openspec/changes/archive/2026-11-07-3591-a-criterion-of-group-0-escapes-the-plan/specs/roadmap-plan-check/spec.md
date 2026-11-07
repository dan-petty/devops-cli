## ADDED Requirements

### Requirement: The plan reader reports a criterion that the model refuses
The plan reader SHALL raise `PlanReadError` for `tasks.md` when `StageCriterion` refuses a criterion line, and the reason SHALL name the line and the problem. Plan-check and plan-recheck SHALL report it as a `read` problem and SHALL print no traceback.

#### Scenario: A criterion of group 0
- **WHEN** the criteria section of `tasks.md` holds the line `Group 0: The command prints one line for each problem`
- **THEN** `read_change` raises `PlanReadError` whose path is `tasks.md` and whose reason names the line.

#### Scenario: Plan-check reads a criterion of group 0
- **WHEN** plan-check reads a change folder whose `tasks.md` holds a criterion of group 0
- **THEN** the output holds one problem with the path `tasks.md` and the rule `read`, and the output holds no traceback.

#### Scenario: Plan-recheck reads a criterion of group 0
- **WHEN** plan-recheck reads a change folder whose `tasks.md` holds a criterion of group 0
- **THEN** the record of the folder holds a refusal of the gate `read`, and the run goes on.

#### Scenario: A criterion of group 1
- **WHEN** the criteria section of `tasks.md` holds the line `Group 1: The command prints one line for each problem`
- **THEN** `read_change` returns a criterion with the group 1.
