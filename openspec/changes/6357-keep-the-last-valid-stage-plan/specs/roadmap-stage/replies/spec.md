## ADDED Requirements

### Requirement: A revision schema failure keeps the last valid plan
A revision reply that fails the schema after its output retry SHALL keep the last schema-valid plan and go back to the planner as one gate return, with that plan as `previous` and the schema violations as the problem. The return SHALL count against `roadmap.stage.gate_returns`. When those returns are spent, the stage MUST end the item with the failure class `parser` and open no pull request.

#### Scenario: A revision schema failure returns the last valid plan
- **WHEN** a fake planner gives a valid first reply, a revision that breaks the schema twice, and then a valid reply
- **THEN** the stage stages the item, the request after the failure holds the earlier plan as `previous`, and the attempt reports one gate return

#### Scenario: The last gate return leaves the parser class
- **WHEN** a fake planner gives a valid first reply and revisions that break the schema until the gate returns of the item are used up
- **THEN** the item fails with `StructuredOutputValidationError`, the attempt reports three gate returns, and the job opens no pull request

#### Scenario: The planner sees the revision schema violations
- **WHEN** the revision error holds the violation `dependences (extra_forbidden)`
- **THEN** the next planner request holds `dependences (extra_forbidden)` in its problem

## MODIFIED Requirements

### Requirement: A reply that breaks the schema returns once
A reply of the first plan ask that fails the schema SHALL go back to the model once, with the field of each violation. A second reply that fails the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations.

#### Scenario: A valid second reply
- **WHEN** the first reply holds a group with an empty `changes` and the second reply is valid
- **THEN** the model gets two requests, the second names `groups[0].changes`, and the item is staged

#### Scenario: A second reply that fails
- **WHEN** both replies hold a blank `documentation`
- **THEN** the model gets two requests, and the item stops with the class `StructuredOutputValidationError`

### Requirement: A toolbox run keeps the return rules of a broken reply
A plan run of the toolbox SHALL send a reply of the first plan ask that breaks the schema back to the model once, with the violations. A second reply that breaks the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations. A reply that the checks of the job refuse SHALL go back once, as it does without the toolbox.

#### Scenario: A reply that breaks the schema twice
- **WHEN** both replies of a plan run hold a group with an empty `changes`
- **THEN** the item stops with the class `StructuredOutputValidationError`

#### Scenario: A missing path after the tools
- **WHEN** the first plan of a toolbox run names a path that the commit lacks
- **THEN** the job asks again with the problem, and a second plan with a missing path stops the item
