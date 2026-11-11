## MODIFIED Requirements

### Requirement: The model picks the type of a title with no Conventional Commit type
For a title with no Conventional Commit type, intake SHALL give the item the type that the model proposes, checked against the `type/*` labels of the package. A labels file with no `type/*` label SHALL NOT stop intake.

#### Scenario: A plain title
- **WHEN** intake places the issue `The board is slow` and the model proposes `type/bug`
- **THEN** the issue gets `type/bug` and no scope label

#### Scenario: A labels file with only scope labels
- **WHEN** `.github/labels.yml` holds only `scope/cli` and intake decides the issue `export the board as CSV`
- **THEN** the model gets every `type/*` label of the package but `type/epic`, each with its description
