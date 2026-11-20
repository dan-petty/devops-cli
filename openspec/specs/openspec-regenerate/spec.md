# openspec-regenerate Specification

## Purpose
`devops openspec regenerate` rewrites the committed OpenSpec skills under the isolated profile. It
reads the version of the `openspec` binary on PATH first, and stops before it writes when that
binary is not the tools lock's version.

## Requirements

### Requirement: Regenerate reads the version before it writes
`devops openspec regenerate` SHALL read the version of the `openspec` binary that it runs, and SHALL exit 1 before it writes any skill when that version is not the one that the `package-lock.json` of the checkout pins or the binary prints none. A binary at the locked version SHALL run `openspec update --force` and exit 0. A dry run SHALL run neither command, write no skill and exit 0.

#### Scenario: An older binary on PATH
- **WHEN** the `openspec_fake` fixture stands for a binary that prints `1.14.3`, the `package-lock.json` of the fake's tree pins another version, and `devops openspec regenerate` runs in that tree
- **THEN** the command exits 1 and the fake records no `openspec update --force` call

#### Scenario: The lockfile of the checkout moves the pin
- **WHEN** the fake binary prints the version of the old pin and the `package-lock.json` of the tree pins `9.9.9`
- **THEN** `devops openspec check` and `devops openspec regenerate` each exit 1, the output names both versions, and the fake records no `openspec update --force` call

#### Scenario: A binary that prints no version
- **WHEN** the fake answers the `--version` run with exit 1 and no output, and `devops openspec regenerate` runs
- **THEN** the command exits 1 and the fake records no `openspec update --force` call

#### Scenario: The locked binary on PATH
- **WHEN** the fake binary prints the version that the `package-lock.json` of the tree pins and `devops openspec regenerate` runs
- **THEN** the command exits 0 and the fake records the `openspec update --force` call

#### Scenario: A dry run with an older binary
- **WHEN** the fake binary prints `1.14.3` and `devops --dry-run openspec regenerate` runs
- **THEN** the command exits 0, the fake records no `--version` call and no `openspec update --force` call, and the skill files of the tree are unchanged

### Requirement: The version finding names the path, the versions and the hint
The error of the version finding of `devops openspec regenerate` SHALL name the binary path, the printed version, the locked version and the install hint.

#### Scenario: The message of the version finding
- **WHEN** the fake binary prints `1.14.3`, the `package-lock.json` of the tree pins another version, and `devops openspec regenerate` runs
- **THEN** the command's error text holds the fake binary path, `1.14.3`, the locked version and the text of `MESSAGES.openspec.missing_hint`, which names `npm ci --ignore-scripts`

### Requirement: One version guard serves check and regenerate
The version guard SHALL be one function of `src/devops_cli/openspec/gate.py` that `check_openspec` and `regenerate` both call, and its version run SHALL go through `OpenSpecTool.run`, so it uses the same opt-out environment and timeout as the version run of the gate.

#### Scenario: Check and regenerate share the finding
- **WHEN** the fake binary prints `1.14.3` and `check_openspec` and `devops openspec regenerate` both run
- **THEN** both report the same `GateCheck.VERSION` detail, and the regenerate run records no `openspec update --force` call

#### Scenario: The environment of the version run
- **WHEN** the fake records the environment of the `--version` run of `devops openspec regenerate`
- **THEN** the recorded call holds `DO_NOT_TRACK`, `OPENSPEC_TELEMETRY`, `OPENSPEC_NO_UPDATE_CHECK` and `OPEN_SPEC_INTERACTIVE`, and the isolated `XDG_CONFIG_HOME` and `HOME` that `OpenSpecTool.run` sets
