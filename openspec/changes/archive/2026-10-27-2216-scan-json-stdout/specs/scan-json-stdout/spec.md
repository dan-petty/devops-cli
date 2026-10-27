# scan-json-stdout Specification

## Purpose
Defines the stdout contract of `devops scan` commands: with `--json` or `--format json`, stdout is a single valid JSON document with no progress output ahead of it.

## ADDED Requirements

### Requirement: JSON stdout parses
The system SHALL write a single valid JSON document to stdout for `devops scan trivy`, `scan secrets`, `scan sast`, `scan iac`, `scan complexity`, `scan workflows` and `scan aibom` when `--json` or `--format json` is set, and SHALL NOT print a progress line to stdout in that mode.

#### Scenario: JSON flag
- **WHEN** the user runs `devops scan trivy . --json`
- **THEN** stdout is a single valid JSON document and the command exits 0

#### Scenario: Format option
- **WHEN** the user runs `devops scan workflows . --format json`
- **THEN** stdout is a single valid JSON document and the command exits 0

#### Scenario: AIBOM format option
- **WHEN** the user runs `devops scan aibom . --format json` without `--output`
- **THEN** stdout is a single valid JSON document and the command exits 0

### Requirement: Table stdout keeps progress
The system SHALL print the muted progress line to stdout for a scan command in table mode.

#### Scenario: Table default
- **WHEN** the user runs `devops scan secrets .`
- **THEN** the command prints its muted progress line and exits 0
