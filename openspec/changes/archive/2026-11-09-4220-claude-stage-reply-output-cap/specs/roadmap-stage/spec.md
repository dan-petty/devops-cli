## ADDED Requirements

### Requirement: A reply cut by the output token limit names the limit
A plan run or a review run of the stage job whose last model reply ends with the finish reason `length` SHALL fail with a `RoadmapStageError` that names the output token limit and `max_tokens`. The failure SHALL NOT be a schema failure, and the record of the failed item SHALL NOT show a count of schema violations for it.

#### Scenario: A plan reply cut by the limit
- **WHEN** the model of a plan run answers with the finish reason `length` and no part
- **THEN** the run raises a `RoadmapStageError` whose message names the output token limit and `max_tokens`
- **AND** the error is not a `StructuredOutputValidationError`

#### Scenario: A review reply cut by the limit
- **WHEN** the model of a review run answers with the finish reason `length` and no part
- **THEN** the run raises the same error

#### Scenario: A stop that the limit did not cause
- **WHEN** a run ends because the reply broke the schema, or because a budget limit was spent
- **THEN** the stop is not marked as a stop by the output token limit
