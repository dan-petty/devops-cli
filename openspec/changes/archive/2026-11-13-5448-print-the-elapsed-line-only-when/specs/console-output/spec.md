## ADDED Requirements

### Requirement: The elapsed line goes only to a terminal
The CLI SHALL write its elapsed line to stderr only when stderr is a terminal, and SHALL write no elapsed line when stderr is a pipe or a file. It MUST decide from the stderr stream itself and MUST ignore the color variables `FORCE_COLOR` and `TTY_COMPATIBLE`.

#### Scenario: A pipe receives no elapsed line
- **WHEN** a person runs a CLI command with stderr connected to a pipe
- **THEN** the stderr of the command holds no elapsed line

#### Scenario: A pseudo-terminal receives the elapsed line
- **WHEN** a person runs a CLI command with stderr connected to a pseudo-terminal
- **THEN** the pseudo-terminal output holds the elapsed line

#### Scenario: A color variable does not enable the line
- **WHEN** a person runs a CLI command with FORCE_COLOR=1 and TTY_COMPATIBLE=1 and stderr connected to a pipe
- **THEN** the stderr of the command holds no elapsed line
