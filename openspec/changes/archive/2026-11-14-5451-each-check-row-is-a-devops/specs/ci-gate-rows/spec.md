## ADDED Requirements

### Requirement: Each row of the check registry is a subcommand
Each row of `get_check_specs()` SHALL be a subcommand of `devops ci` named after the row, and a row with no hand-written command SHALL get a generated command that runs the same path as `devops ci --only <row>`: the same gate slot, the same telemetry and the same request plan of a narrowed run. The list of commands SHALL come from a static tuple of row names, and the module SHALL NOT call `get_check_specs()` while it imports.

#### Scenario: A row with no hand-written command
- **WHEN** The test runs the row constructs and the row test-tree, each with `--dry-run`.
- **THEN** Each run exits 0, and its request plan holds one request for each command of that row's check spec and no request of another row.

#### Scenario: A row with a hand-written command
- **WHEN** The test runs the lint row with `--dry-run`.
- **THEN** The run exits 0 and plans the fix command of the lint row, which is its hand-written command.

### Requirement: The static row tuple matches the registry
The static tuple of row names in `src/devops_cli/commands/ci.py` SHALL hold the same names, in the same order, as `get_check_specs()`, so that a row that is added, renamed or removed fails the test that compares the two lists.

#### Scenario: A row is added, renamed or removed
- **WHEN** The test compares the static tuple with the names that `get_check_specs()` returns.
- **THEN** The two lists are equal, and the test names the first name that differs.

### Requirement: `--only` and `--skip` select a set of rows
`--only` and `--skip` SHALL accept a comma-separated list and a repeated option, and SHALL select exactly the named rows, so that the form `--only lint,format,domain` of `.pre-commit-config.yaml` keeps working.

#### Scenario: A comma-separated list of two rows
- **WHEN** The test runs the `ci` group with `--only constructs,openspec --dry-run`.
- **THEN** The run exits 0, and its request plan holds the commands of both rows and no command of another row.

#### Scenario: A repeated option
- **WHEN** The test runs the `ci` group with `--only constructs --only openspec --dry-run`.
- **THEN** The run exits 0, and its request plan holds the commands of both rows and no command of another row.

### Requirement: A wrong row name is a usage error with a close name
A row name that the registry does not hold MUST raise `BadParameter` from the option callback, with up to 3 close row names and the valid row names. The root group MUST record one usage error of kind `bad_value` with command path `ci`, and the run MUST exit 2.

#### Scenario: A misspelled row name of the only option
- **WHEN** The test runs the root CLI with `ci --only constructz`.
- **THEN** The run exits 2, its error text holds `constructs`, and the usage ledger holds one record of kind `bad_value` and command path `ci`.

#### Scenario: A misspelled row name of the skip option
- **WHEN** The test runs the root CLI with `ci --skip constructz`.
- **THEN** The run exits 2, and the usage ledger holds one record of kind `bad_value` and command path `ci`.

### Requirement: The help of the selection options names the rows
The help of `--only` and `--skip` MUST list the row names of the static tuple, so that a caller reads the valid names without a second command.

#### Scenario: A person reads the help of the group
- **WHEN** The test runs `devops ci --help`.
- **THEN** The help text of `--only` and of `--skip` holds each row name of the static tuple.

### Requirement: `devops ci run` is removed
`devops ci run` MUST NOT exist. The root group MUST report the word `run` as an unknown command and exit 2. The text of the removed command MUST NOT appear in `README.md`, in a file under `docs/` or `src/`, or in a test module other than the case that searches for it.

#### Scenario: The removed command
- **WHEN** The test runs the root CLI with `ci run`.
- **THEN** The run exits 2, and the usage ledger holds one record of kind `unknown_command` with command path `ci`.

#### Scenario: No other file names the removed command
- **WHEN** The test searches the tracked files with `git grep` and leaves its own module out.
- **THEN** The search finds no line.

### Requirement: The gate-slot metric description names no removed command
The description of the `CI_GATE_SLOT_WAIT` histogram SHALL be `Time a gate run waited for a free gate slot before its checks started`, which names no command and holds no removed command name.

#### Scenario: The description of the gate-slot histogram
- **WHEN** The test reads the description of `CI_GATE_SLOT_WAIT`.
- **THEN** The description equals `Time a gate run waited for a free gate slot before its checks started`.
