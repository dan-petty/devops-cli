## ADDED Requirements

### Requirement: The group measure and the Job use one token counter
The stage SHALL count the tokens of a task group with the same tiktoken encoding as the implement Job, and SHALL raise an error that names the missing tiktoken cache when the encoding cannot be loaded.

#### Scenario: Both paths count the same text
- **WHEN** The stage and the implement Job count the same task-group text and the tiktoken cache is present
- **THEN** Both give the same token count

#### Scenario: The token cache is missing
- **WHEN** A plan run measures a task group and the tiktoken cache is missing
- **THEN** The run fails with an error that names the missing cache and no character count is used

### Requirement: A created file counts its estimated lines
The stage SHALL add 32 tokens for each estimated line of a path in the `creates` of a task group to the token count of that group, and SHALL refuse a group whose `creates` path has no line estimate with an error that names the path.

#### Scenario: A group creates a 1,500-line file
- **WHEN** A task group has a `creates` entry with a 1,500-line estimate and no other input
- **THEN** The stage counts the group as 48,000 tokens and refuses it as over the 40,000-token budget

#### Scenario: A creates path has no estimate
- **WHEN** A task group creates a file and the reply gives no line estimate for that path
- **THEN** The stage refuses the group with an error that names the path

### Requirement: The staging prompt states the budget and the estimate rule
The staging prompt SHALL state the 40,000-token step budget and the rule that each `creates` path carries a line estimate.

#### Scenario: The prompt states both limits
- **WHEN** The staging prompt of a plan run is loaded
- **THEN** It holds the 40,000-token budget and the line-estimate rule for each `creates` path
