## ADDED Requirements

### Requirement: devops config show prints the model tier ladder
`devops config show` SHALL print the model tier ladder, with the tier of each attempt of each step class.

#### Scenario: The ladder is shown
- **WHEN** a ladder is set and `devops config show` runs
- **THEN** the output lists the tier for each attempt of each step class
