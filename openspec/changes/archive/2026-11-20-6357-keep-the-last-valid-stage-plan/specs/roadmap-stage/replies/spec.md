## ADDED Requirements

### Requirement: A schema failure after an earlier plan keeps that plan
A reply to a gate return or to a repair round that fails the schema after its output retry SHALL go back to the planner as one gate return, with the earlier schema-valid plan of that request as `previous` and, as the problem, the problem of that request and the schema violations.

#### Scenario: A revision schema failure returns the last valid plan
- **WHEN** a fake planner gives a valid first reply, a revision that breaks the schema twice, and then a valid reply
- **THEN** the stage stages the item, the request after the failure holds the earlier plan as `previous`, and the attempt reports one gate return

#### Scenario: A gate return schema failure returns the refused plan
- **WHEN** the checks refuse the first reply for a missing path, and the reply to the return breaks the schema
- **THEN** the next request holds the refused plan as `previous` and a problem that names the missing path and the violations, and the attempt reports two gate returns

#### Scenario: The planner sees the revision schema violations
- **WHEN** the revision error holds the violation `dependences (extra_forbidden)`
- **THEN** the next planner request holds `dependences (extra_forbidden)` and the findings of the review in its problem

### Requirement: Schema returns share the gate returns
A schema return SHALL count against `roadmap.stage.gate_returns`, in the same count as the returns of the checks. When those returns are spent, a reply that fails the schema MUST end the item with the failure class `parser`, and the job MUST open no pull request.

#### Scenario: The last gate return leaves the parser class
- **WHEN** a fake planner gives a valid first reply and revisions that break the schema until the gate returns of the item are used up
- **THEN** the item fails with `StructuredOutputValidationError`, the attempt reports three gate returns, and the job opens no pull request

#### Scenario: The last return of the checks leaves the parser class
- **WHEN** the checks refuse the first reply, and each reply after it breaks the schema
- **THEN** the item fails with the class `parser` after 4 planner requests, and the attempt reports three gate returns

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
