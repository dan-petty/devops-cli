## MODIFIED Requirements

### Requirement: A refused revision of a repair round returns
A revision of a repair round that the checks refuse SHALL go back to the planner with the refused revision as `previous` and the problem as `problem`, as a refused first reply does: `roadmap.stage.gate_returns` times (default 3) for each repair round, and the extra return of the item when `roadmap-stage/returns` grants it (#4851). A revision that the checks accept SHALL cause no extra planner call. A revision that is a placeholder in every text SHALL end the item with no return.

#### Scenario: The first revision is refused and the second passes
- **WHEN** the checks refuse the first revision of a repair round and accept the second
- **THEN** the planner gets a third request with `previous` set to the refused revision and `problem` set to the problem of the checks, and the job stages the second revision

#### Scenario: The returns follow the setting
- **WHEN** `roadmap.stage.gate_returns` is 2 and the checks refuse each revision of a repair round with the same problem
- **THEN** the planner gets two returns for the round and no third

#### Scenario: The revision passes
- **WHEN** the checks accept the first revision of a repair round
- **THEN** the planner gets no return for the round
