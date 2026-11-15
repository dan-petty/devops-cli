## ADDED Requirements

### Requirement: The inbox line names the follow command of its item
Each inbox line that is about an item SHALL hold the follow command with the number of that item, and a line whose number is a pull request's SHALL hold no follow command.

#### Scenario: A line of a blocked item
- **WHEN** A test renders the inbox of one blocked item.
- **THEN** The line of the item holds the follow command followed by the number of the item.

#### Scenario: A line of the plan pull request of an item
- **WHEN** A test renders the inbox of one item whose job record names its plan pull request.
- **THEN** The line of the pull request holds no follow command.
