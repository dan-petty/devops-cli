# Spec Delta

## MODIFIED Requirements

### Requirement: The raised limits fit the windows of the stack
The default step budget and the turn reserve SHALL fit the default context window of the implement task. The output cap of a reply, the packed file and the tool result of a step SHALL fit that window too. The body that the alternatives check sends SHALL be at most a quarter of the window of the task `alternatives` that the example ConfigMap sets.

#### Scenario: The step budget and the reserve
- **WHEN** the default step budget and the turn reserve are added
- **THEN** the sum is not above the default window of the implement task

#### Scenario: The alternatives body
- **WHEN** the example ConfigMap sets the window of the `alternatives` task
- **THEN** the body cap of the alternatives check is at most a quarter of that window

#### Scenario: The output cap and the inputs
- **WHEN** the output cap of a reply and the default step budget are added
- **THEN** the sum is not above the default window of the implement task
