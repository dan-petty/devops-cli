## ADDED Requirements

### Requirement: A tool call with invalid arguments names the cause
A plan run or a review run of the stage job that ends because a tool call of its last model reply holds arguments that are not valid JSON SHALL fail with a `RoadmapStageError` that names the tool call with invalid arguments. The failure SHALL NOT be a schema failure, and the record of the failed item SHALL NOT show a count of schema violations for it.

#### Scenario: A plan call with joined arguments
- **WHEN** the last reply of a plan run holds a call to a tool with arguments of two JSON objects joined in one text
- **THEN** the run raises a `RoadmapStageError` whose message names a tool call with invalid arguments
- **AND** the error is not a `StructuredOutputValidationError`

#### Scenario: A review call with invalid arguments
- **WHEN** the last reply of a review run holds a call with arguments that are not valid JSON
- **THEN** the run raises the same error

#### Scenario: A stop that invalid arguments did not cause
- **WHEN** a run ends because the reply broke the schema with valid JSON, or because a budget limit was spent
- **THEN** the stop is not marked as a stop by invalid arguments
