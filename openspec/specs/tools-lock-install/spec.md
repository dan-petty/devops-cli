# tools-lock-install Specification

## Purpose
The tools lock pins each tool at an exact version, and `devops install-tools` reports each tool whose command on PATH is not at its pin.

## Requirements

### Requirement: The check reads the version the openspec command prints
`devops install-tools --check` SHALL run the `openspec` command that PATH resolves with `--version`, SHALL compare the first non-empty line of its output with the version in the tools lock, and SHALL print the path of that command with the locked version when the two match.

#### Scenario: An older command fails the check
- **WHEN** the `openspec` command on PATH prints `1.14.3` and the tools lock pins `1.17.0`
- **THEN** the output names the command path, `1.14.3` and `1.17.0`, and the exit code is 1

#### Scenario: The locked command passes the check
- **WHEN** the `openspec` command on PATH prints `1.17.0`, the tools lock pins `1.17.0`, and the command in the target directory links to the locked version
- **THEN** the output holds `openspec 1.17.0` and the path of the command, and the exit code is 0

#### Scenario: A command that prints no version fails the check
- **WHEN** the `openspec` command on PATH exits 1
- **THEN** the output says that the version of the command path cannot be read, and the exit code is 1

#### Scenario: A path with no command keeps the link check
- **WHEN** PATH resolves no `openspec` command and the command in the target directory links to the locked version
- **THEN** the output holds no version line and the exit code is 0

### Requirement: Only-missing installs openspec when PATH holds another version
`devops install-tools --only-missing` SHALL install the locked `openspec` when the command on PATH prints another version than the tools lock.

#### Scenario: An older command is replaced
- **WHEN** the command in the target directory links to the locked version, the `openspec` command on PATH prints `1.14.3`, and the tools lock pins `1.17.0`
- **THEN** the command runs the `npm ci` install for `openspec` and the command in the target directory links to the locked version
