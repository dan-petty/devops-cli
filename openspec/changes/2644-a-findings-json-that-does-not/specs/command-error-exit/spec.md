## ADDED Requirements

### Requirement: review-session-file-validation-error
When a review session file fails ReviewSessionPayload validation, the command SHALL raise the project's ValidationError with a message that names the file path and the dotted field path of each validation failure, and SHALL exit with a non-zero code and no traceback.

#### Scenario: Loader raises project error on invalid file
- **WHEN** A findings.json file fails ReviewSessionPayload validation
- **THEN** The loader raises the project's ValidationError, not pydantic's ValidationError

#### Scenario: Message contains file path and field path
- **WHEN** A required field is missing in a findings.json file
- **THEN** The error message contains the file path and the dotted field path such as network_references.0.reputation.outcome

#### Scenario: Clean exit on invalid file
- **WHEN** A findings.json file fails validation and the command runs
- **THEN** The process exits with a non-zero code and the output contains no Python traceback
