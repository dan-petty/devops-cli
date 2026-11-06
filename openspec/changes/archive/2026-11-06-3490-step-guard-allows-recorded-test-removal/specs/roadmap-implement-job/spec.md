## ADDED Requirements

### Requirement: The job reads the record of a removal from the default branch
The job SHALL give each step the tests that the `## Weakened checks` section of the plan on `origin/<default>` names as `path::name`. The job MUST NOT read that record from the checkout, because the agent can edit the checkout. A plan that is not on the default branch records no test. A section that the plan reader refuses SHALL leave the item out of the plan of a run. When the default branch gets such a section after that plan, the job SHALL stop the item with the class `plan_defect`.

#### Scenario: A merged plan records the removal
- **WHEN** the plan on the default branch names `tests/test_old.py::test_a`, and the step removes that test
- **THEN** the step reports done, and the job goes on to the next group

#### Scenario: The agent writes the record
- **WHEN** the plan on the default branch records nothing, and the agent adds an entry to the `proposal.md` of the checkout and removes the test
- **THEN** the item stops with the class `tests_lost` and the action `wait`

#### Scenario: A section in another form at the plan of a run
- **WHEN** the section on the default branch holds a line that the plan reader refuses
- **THEN** the plan leaves the item out, and the reason holds the line

#### Scenario: A section in another form after the plan of a run
- **WHEN** the default branch gets such a line after the plan selected the item
- **THEN** the item stops with the class `plan_defect` before the step calls the model
