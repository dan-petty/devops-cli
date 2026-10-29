## ADDED Requirements

### Requirement: The tflint adapter reads the report that tflint writes
The tflint adapter SHALL run `tflint --format json`, with `--config <file>` when the caller names an existing config file, in the directory of the target. It SHALL give one finding for each item of `issues` in the one JSON object that tflint writes, with the severity `error` as HIGH, `warning` as MEDIUM and `info` as LOW. A run that exits 2 with issues SHALL be a scan that ran. A run that exits 1 with no issue SHALL be a failed scan.

#### Scenario: tflint reports an issue of each severity
- **WHEN** tflint exits 2 and writes a report with one issue of severity `error`, one of `warning` and one of `info`
- **THEN** the scan ran, and its findings are one HIGH, one MEDIUM and one LOW finding, in the order of the report, each at `<file>:<line>` of its range

#### Scenario: tflint reports an error and no issue
- **WHEN** tflint exits 1 and writes `{"issues": [], "errors": [{"severity": "error", "message": "boom"}]}`
- **THEN** the scan failed and has no finding

#### Scenario: tflint finds nothing
- **WHEN** tflint exits 0 and writes `{"issues": [], "errors": []}`
- **THEN** the scan ran and has no finding

### Requirement: The tflint adapter keeps no hand-written fallback
The tflint adapter SHALL keep no built-in patterns. When no directory of PATH holds tflint, the scan SHALL be `unavailable` with the reason `Binary 'tflint' not found on PATH`, and SHALL have no finding, whatever the `.tf` files of the target hold.

#### Scenario: tflint is not installed
- **WHEN** no directory of PATH holds tflint, and the adapter scans a directory with a security group open to `0.0.0.0/0`
- **THEN** the outcome status is `unavailable`, the reason is `Binary 'tflint' not found on PATH`, and the outcome has no finding

### Requirement: Every scanner of the registry has a pinned program
The program of each scanner of the default registry SHALL be a command of a tool in `tools.lock`, or a pinned dev dependency of `pyproject.toml`. The registry SHALL hold no scanner for another program.

#### Scenario: A scanner names a program that nothing pins
- **WHEN** a test reads the program of each scanner of the default registry
- **THEN** each program is a command of `tools.lock` or the dev dependency zizmor

### Requirement: No scanner or command runs dive
The scanner registry SHALL hold no scanner named `dive`. The `devops docker` commands SHALL include no `analyze-layers` command.

#### Scenario: The registry lists its scanners
- **WHEN** a test lists the scanners of the default registry
- **THEN** the list has 13 scanners, and none is named `dive`

#### Scenario: The docker command group lists its commands
- **WHEN** `devops docker analyze-layers alpine:latest` runs
- **THEN** the command exits 2 and says that the command does not exist
