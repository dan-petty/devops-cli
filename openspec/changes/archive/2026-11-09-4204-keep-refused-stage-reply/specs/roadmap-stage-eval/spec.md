## ADDED Requirements

### Requirement: The live report counts the degenerate cases
The live run SHALL end a case with the outcome `degenerate` when the stage planner stops it on a reply that is a placeholder in every text, and the report SHALL show the count of such cases in the line of how the cases ended, `0` when there are none.

#### Scenario: A reply of placeholders
- **WHEN** the model answers a case with `x` or `placeholder` in every text of the plan
- **THEN** the case ends `degenerate` after one model call, and the report shows `degenerate 1`

#### Scenario: A run with no such reply
- **WHEN** the live run finishes and no reply is a placeholder in every text
- **THEN** the report shows `degenerate 0`
