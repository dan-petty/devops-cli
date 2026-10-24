# Spec Delta

## Purpose

The record of each run of a review tool names the tool, its version and the digest of the code that ran, so that two reviews show whether the same tools ran.

## ADDED Requirements

### Requirement: The binary digest of a Python review tool names its installed distribution
When a console script of an installed distribution wrote the launcher of a review tool, the record of a run SHALL name that distribution, from the site-packages directories that `sysconfig` gives for the environment of the launcher. The `version` SHALL be its version. The `binary_sha256` SHALL be the SHA-256 of the file hashes in its `RECORD`, less the launcher scripts, else `unavailable` when it has no `RECORD`.

#### Scenario: Only the launcher changes
- **WHEN** Bandit is installed again in its environment with the same package files and a launcher that names another interpreter
- **THEN** the `binary_sha256` of Bandit stays the same
- **AND** it is not the SHA-256 of the launcher file

#### Scenario: A file of the package changes
- **WHEN** Bandit is installed again in its environment with one changed file in its package
- **THEN** the `binary_sha256` of Bandit changes and its `version` stays the same

#### Scenario: A Python tool at a version that the lock does not pin
- **WHEN** the Semgrep on PATH is a launcher of the Semgrep distribution at version 1.0.0
- **THEN** the `version` of Semgrep is 1.0.0

#### Scenario: A distribution without a RECORD
- **WHEN** the Bandit on PATH is a launcher of a Bandit distribution that has no `RECORD`
- **THEN** the `binary_sha256` of Bandit is `unavailable`

### Requirement: The binary digest of a native review tool is the digest of its file
When no distribution in those directories has a console script that wrote the program of a review tool, the `binary_sha256` of a run SHALL be the SHA-256 of the program file.

#### Scenario: A native binary
- **WHEN** the kube-linter on PATH is one binary file, and the Ruff on PATH is the binary that the Ruff distribution ships as a file and not as a console script
- **THEN** the `binary_sha256` of each is the SHA-256 of its file
- **AND** the `version` of kube-linter is the version that `tools.lock` pins
