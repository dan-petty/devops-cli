## ADDED Requirements

### Requirement: The replay of the golden set runs once per test module
The eval gate test module SHALL compute the replay of the golden set once in a module-scoped fixture, and SHALL give each case of the set its own parametrized test item.

#### Scenario: One item for each case
- **WHEN** A test reads the parametrize mark of the case test in the eval gate test module
- **THEN** The mark's values are the list that load_cases returns, so pytest collects one item for each case.

#### Scenario: The report tests share one replay
- **WHEN** A test reads the source of the eval gate test module
- **THEN** The whole-set replay_all call sits in the module-scoped fixture, and no report test calls replay_all itself.
