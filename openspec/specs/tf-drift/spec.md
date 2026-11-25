# tf-drift Specification

## Purpose

Specify exit codes, unlocked saved-plan execution, and check evaluation for `devops tf drift`.

## Requirements

### Requirement: Drift plan command flags

The drift plan SHALL run `tofu plan -refresh-only -detailed-exitcode -lock=false -out=<plan file>` and SHALL NOT pass `-json`.

#### Scenario: Drift plan argv

- **WHEN** a test calls `read_plan_drift` on an initialized directory with a process fake recording calls
- **THEN** the recorded `tofu plan` argv includes `-refresh-only`, `-detailed-exitcode`, `-lock=false`, and `-out=<plan file>`, and does not include `-json`

### Requirement: Check results read from the saved plan

`read_plan_drift` MUST inspect top-level `checks` entries from `tofu show -json <plan file>`, collecting `address.to_display` for `fail`/`error` into `failed_checks` and `unknown` into `unknown_checks`.

#### Scenario: Failed and unknown checks

- **WHEN** `tofu plan` succeeds and `tofu show -json <plan file>` returns one `fail` or `error` check and one `unknown` check
- **THEN** `PlanDriftResult.failed_checks` contains the failing check's `address.to_display` and `PlanDriftResult.unknown_checks` contains the unknown check's `address.to_display`

### Requirement: Exit 2 on drift

`devops tf drift` SHALL exit `2` when the plan reports changes or `IaCDriftReport.drift_detected` is true (unless a plan error or failed/unknown check forces exit `1`).

#### Scenario: Recorded replay with drift

- **WHEN** `tofu plan` returns exit code `2` and `tofu show -json <plan file>` reports drifted resources
- **THEN** `devops tf drift` prints the drift report and exits `2`

### Requirement: Exit 0 on a clean stack

`devops tf drift` SHALL exit `0` when the plan returns `0`, all checks pass, and no divergence exists.

#### Scenario: No drift

- **WHEN** `tofu plan` returns `0`, `checks` contains only `pass` entries, and resources match state
- **THEN** `devops tf drift` prints the in-sync message and exits `0`

### Requirement: Exit 1 on a failed or unknown check

`devops tf drift` SHALL print affected `address.to_display` values and exit `1` when any check has status `fail`, `error`, or `unknown`, overriding drift exit code `2`.

#### Scenario: Failed check with drift

- **WHEN** `tofu plan` returns `2` with drifted resources and `tofu show -json <plan file>` holds a `fail` check
- **THEN** `devops tf drift` prints the drift table and failed check address, and exits `1`

### Requirement: Exit 1 on a plan error

`devops tf drift` SHALL exit `1` and surface stderr when `tofu plan` returns an exit code other than `0` or `2`, without running `tofu show` on the plan file.

#### Scenario: Plan error

- **WHEN** `tofu plan` returns exit code `1` with stderr `Error: backend unavailable`
- **THEN** `read_plan_drift` returns `plan_returncode == 1` and `plan_error == "Error: backend unavailable"`, skips `tofu show <plan file>`, and `devops tf drift` exits `1` with that error in output

### Requirement: Serialized output keeps the exit code

`devops tf drift --format json` MUST emit the serialized payload before exiting `2` on drift or `1` on failed/unknown checks or plan errors.

#### Scenario: JSON output on drift

- **WHEN** `devops tf drift --format json` runs on a stack with drift
- **THEN** stdout contains the JSON drift report and the command exits `2`

### Requirement: Uninitialized directory result

`read_plan_drift` SHALL return an empty `PlanDriftResult` (`plan_returncode == 0`, empty lists) with zero subprocess calls when `.terraform` does not exist.

#### Scenario: Uninitialized directory

- **WHEN** `read_plan_drift` is called on a directory lacking `.terraform`
- **THEN** it returns an empty `PlanDriftResult` and records zero process fake calls

### Requirement: Exit codes in the command help

`devops tf drift --help` SHALL document exit codes `0` (clean), `1` (failed/unknown check or plan error), and `2` (drift), and `docs/commands/tf.md` SHALL stay synchronized via `devops docs generate`.

#### Scenario: Help text

- **WHEN** a user runs `devops tf drift --help`
- **THEN** the help output describes exit codes `0`, `1`, and `2`
