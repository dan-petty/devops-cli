# console-output Specification

## Purpose
Provides formatted and leveled console output for the command-line interface, including level prefixes, styling, and stream routing.

## Requirements

### Requirement: Leveled print functions format messages without caller prefix duplication

The console output system SHALL format leveled console messages with standard level prefixes. Callers SHALL NOT include the level prefix symbol in the message argument passed to `print_success`, `print_error`, `print_warning`, `print_info`, or `print_step`.

#### Scenario: Success message formatting without duplicated prefix
- **WHEN** `print_success` is called with a success message string
- **THEN** the output stream receives the message prefixed by exactly one check mark symbol

#### Scenario: Leveled print call invariant enforcement
- **WHEN** tests validate source code calls to leveled print functions across `src/devops_cli`
- **THEN** no call passes a string argument that begins with the level prefix symbol of that function

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
