# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: The check reads the context window of the analysis task`
- TO: `### Requirement: The check reads the context window of the alternatives task`

## MODIFIED Requirements

### Requirement: The check reads the context window of the alternatives task
The run of one item SHALL pass the context window of the `alternatives` task to the investigation, so that the window ends the tools of the run before the counts do.

#### Scenario: The window reaches the run
- **WHEN** an item is checked and the window of the `alternatives` task is 65536 tokens
- **THEN** the investigation gets the window 65536
