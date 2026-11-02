## ADDED Requirements

### Requirement: The live run plans with the toolbox unless told not to
`devops roadmap eval stage` SHALL plan each case with the toolbox of the stage job. With `--no-toolbox` it SHALL plan each case with one model call and no tool. Both modes SHALL print the same table and store a report of the same shape, so two runs of one model compare.

#### Scenario: The default run
- **WHEN** a live run plans a case with a scripted model that calls `read_file` once and then answers
- **THEN** the model gets the tool, and the case counts as before

#### Scenario: Without the toolbox
- **WHEN** the run has `--no-toolbox`
- **THEN** the model gets one request with no tool, and the table has the same rows

## MODIFIED Requirements

### Requirement: A group holds the eval commands
The command group `devops roadmap eval` SHALL hold the golden-set commands. The command `stage` SHALL be one of them, with the options `--case`, `--model`, `--limit`, `--json`, `--dry-run`, `--replay` and `--no-toolbox`.

#### Scenario: The command is found
- **WHEN** the user runs `devops roadmap eval --help`
- **THEN** the output lists `stage`
