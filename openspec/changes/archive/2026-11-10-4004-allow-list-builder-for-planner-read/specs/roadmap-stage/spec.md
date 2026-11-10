## ADDED Requirements

### Requirement: The allow-list holds the read-only rows of the exposure table
The builder SHALL hold each command path whose row of `CONST_MCP_EXPOSURE_TABLE` is read-only and whose permitted parameters hold no path parameter, with the permitted parameter names as its value.

#### Scenario: A read-only command with no path parameter
- **WHEN** the builder runs and the row of `gh labels list` is read-only and its permitted parameters hold no path parameter
- **THEN** the table holds `('gh', 'labels', 'list')` with `repo` among its parameters

### Requirement: A path parameter keeps its command out of the allow-list
The builder SHALL leave out each command path whose permitted parameters hold a path parameter: a parameter that Typer types as a path, or a parameter that `PATH_CONFINEMENTS` names for the command.

#### Scenario: A restricted command with a path parameter
- **WHEN** the allowed set of `tf plan` holds a directory parameter that Typer types as a path
- **THEN** the table holds no entry for `('tf', 'plan')` and the validator returns the reason `path option`

#### Scenario: An unrestricted command with a path parameter
- **WHEN** the repository parameter of `ai read` has a path type
- **THEN** the table holds no entry for `('ai', 'read')` and the validator returns the reason `path option`

#### Scenario: A text parameter that holds a path
- **WHEN** the builder runs and `scan sast` permits `config`, which holds a path and which no type shows
- **THEN** the table holds no entry for `('scan', 'sast')` and the validator returns the reason `path option`

### Requirement: A restricted command permits only its allowed options
The builder SHALL take the permitted options of a command that `_PATH_PARAM_RESTRICTIONS` names from that entry's `allowed` set.

#### Scenario: A restricted command with no path parameter
- **WHEN** the builder runs and the entry of `telemetry profile` allows one option
- **THEN** the table holds `('telemetry', 'profile')` with that option as its only one

### Requirement: The help form of a command path is permitted
The validator SHALL permit the `--help` form of each command path that the Click tree resolves and SHALL return no reason for it.

#### Scenario: Help of a write command
- **WHEN** the validator checks `valkey flush` with the `--help` option
- **THEN** it permits the run and returns no reason

### Requirement: A refused run names the path and one reason
The validator SHALL return the command path and one reason from `unknown command`, `not read-only`, `path option` and `option not permitted` for a run that it refuses, and SHALL name the option for `option not permitted`.

#### Scenario: A command path that no row names
- **WHEN** the validator checks `config unset`
- **THEN** it refuses the run with the reason `unknown command` and names the path `('config', 'unset')`

#### Scenario: An option outside the permitted set
- **WHEN** the validator checks `ai benchmark` with the `output` option
- **THEN** it refuses the run with the reason `option not permitted` and names `output`
