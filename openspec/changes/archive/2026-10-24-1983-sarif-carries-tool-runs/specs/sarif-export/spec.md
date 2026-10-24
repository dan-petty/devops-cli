# Spec Delta

## Purpose

The SARIF 2.1.0 documents that devops-cli writes for a scan and for a review, and what each run of a document holds.

## ADDED Requirements

### Requirement: The SARIF run of a review tool holds the records of that tool

The SARIF document of a review SHALL hold each `ToolRun` record of a tool in the property bag of the run of that tool, under `tool_runs`, with the field names of `ToolRun` and in the order of the runs. The run SHALL hold no `invocations`, no `artifacts` and no `versionControlProvenance` from a record. The document SHALL validate against the SARIF 2.1.0 JSON schema.

#### Scenario: A tool that gave a result

- **WHEN** a review writes `findings.sarif`, and Gitleaks ran twice and gave one result
- **THEN** the run of Gitleaks holds the two records of Gitleaks under `tool_runs`, and `ToolRun` reads each one back with no change
- **AND** the run holds no `invocations`, no `artifacts` and no `versionControlProvenance`
- **AND** the document validates against the SARIF 2.1.0 JSON schema

### Requirement: A record gives no tool a run

A tool that has records and no result SHALL have no run in the SARIF document of a review, because a record does not say that its tool succeeded.

#### Scenario: A tool that gave no result

- **WHEN** Bandit ran in the review and gave no result
- **THEN** the SARIF document of the review has no run for Bandit

### Requirement: The driver names the version of the records when no result names one

The driver of the run of a tool SHALL name the version that a result of the tool names. When no result names a version, the driver SHALL name the version of the records of the tool if they name one version, and no version if they name two or more.

#### Scenario: No result names a version

- **WHEN** no result of Gitleaks names a version, and each record of Gitleaks names one version
- **THEN** the driver of the run of Gitleaks names that version

#### Scenario: A result names a version

- **WHEN** a result of Gitleaks names a version, and the records name another
- **THEN** the driver names the version of the result

#### Scenario: The records name two versions

- **WHEN** no result of Gitleaks names a version, and the records of Gitleaks name two versions
- **THEN** the driver names no version
