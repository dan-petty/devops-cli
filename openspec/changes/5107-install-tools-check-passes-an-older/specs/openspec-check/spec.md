## ADDED Requirements

### Requirement: The gate reads the version of the command on PATH
`devops openspec check` SHALL run `openspec --version` before its other checks and SHALL report one problem naming the printed version, the locked version, the command path and `uv run devops install-tools --tool openspec --only-missing` when the printed version differs from the tools lock.

#### Scenario: An older command replaces the skill advice
- **WHEN** the `openspec` command on PATH prints `1.14.3`, the tools lock pins `1.17.0`, and a committed skill differs from a regeneration
- **THEN** the output holds `1.14.3`, `1.17.0` and `uv run devops install-tools --tool openspec --only-missing`, holds no `regenerate`, and the gate ran no `openspec update --force`

#### Scenario: The locked command keeps the skill check
- **WHEN** the `openspec` command on PATH prints the version that the tools lock pins and a committed skill differs from a regeneration
- **THEN** the output holds the skill path and `uv run devops openspec regenerate`
