# sarif-export Specification

## Purpose
The SARIF 2.1.0 documents that devops-cli writes for a scan and for a review, and what each run of a document holds.

## Requirements

### Requirement: The SARIF run of a review tool holds the records of that tool

The SARIF document of a review SHALL hold each `ToolRun` record of a tool in the property bag of the run of that tool, under `tool_runs`, with the field names of `ToolRun` and in the order of the runs. The run SHALL hold no `artifacts` from a record. The document SHALL validate against the SARIF 2.1.0 JSON schema.

#### Scenario: A tool that gave a result

- **WHEN** a review writes `findings.sarif`, and Gitleaks ran twice and gave one result, and no record of Gitleaks has a `repository_uri`
- **THEN** the run of Gitleaks holds the two records of Gitleaks under `tool_runs`, and `ToolRun` reads each one back with no change
- **AND** the run holds no `artifacts` and no `versionControlProvenance`
- **AND** the document validates against the SARIF 2.1.0 JSON schema

### Requirement: The run names each revision of the records of its tool

The run SHALL hold one `versionControlProvenance` entry, with `repositoryUri` and `revisionId`, for each distinct pair of `repository_uri` and `commit` among the records of the tool whose `repository_uri` is set and whose `commit` is set and does not end with `-dirty`, in the order of the first record of each pair. The run SHALL hold no `versionControlProvenance` when no record has such a pair.

#### Scenario: Clean commit with repository

- **WHEN** a record of Gitleaks has `repository_uri` set and a commit that does not end with `-dirty`
- **THEN** the run of Gitleaks has one `versionControlProvenance` entry with that `repositoryUri` and that commit as `revisionId`
- **AND** the document validates against the SARIF 2.1.0 JSON schema

#### Scenario: Dirty commit

- **WHEN** a record of Gitleaks has `repository_uri` set and a commit that ends with `-dirty`
- **THEN** the run of Gitleaks has no `versionControlProvenance`

#### Scenario: No repository

- **WHEN** a record of Gitleaks has a clean commit and `repository_uri` None
- **THEN** the run of Gitleaks has no `versionControlProvenance`

#### Scenario: No commit

- **WHEN** a record of Gitleaks has `repository_uri` set and commit None
- **THEN** the run of Gitleaks has no `versionControlProvenance`

#### Scenario: Records with different commits

- **WHEN** Gitleaks ran three times with the same `repository_uri`, at the clean commits A, B and A
- **THEN** the run of Gitleaks has two `versionControlProvenance` entries, one for the commit A and one for the commit B, in that order
- **AND** the document validates against the SARIF 2.1.0 JSON schema

#### Scenario: Clean and dirty records

- **WHEN** Gitleaks ran twice with the same `repository_uri`, once at a clean commit and once at a commit that ends with `-dirty`
- **THEN** the run of Gitleaks has one `versionControlProvenance` entry, for the clean commit

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

### Requirement: Each tool that has a record has a run

The SARIF document of a review SHALL have a run for each tool that gave a result or has a record. A run of a tool that gave no result SHALL have an empty `results` array when every record of the tool succeeded, and no `results` property when a record of the tool did not succeed or is not settled.

#### Scenario: A tool that gave no result and succeeded

- **WHEN** Bandit ran in the review, its run succeeded, and it gave no result
- **THEN** the SARIF document of the review has a run for Bandit with an empty `results` array

#### Scenario: A tool that gave no result and failed

- **WHEN** Bandit ran in the review, its run failed, and it gave no result
- **THEN** the run of Bandit has no `results` property
- **AND** the document validates against the SARIF 2.1.0 JSON schema

### Requirement: Each settled record is one invocation of the run of its tool

The run of a tool SHALL hold one invocation for each record of the tool whose success is known, in the order of the runs. An invocation SHALL hold `executionSuccessful`, the success of the record, and `exitCode` when the record holds an exit code. It SHALL hold no `exitCode` when the run ended on a signal or timed out. A record whose success is not known SHALL have no invocation.

#### Scenario: Two settled runs of one tool

- **WHEN** Gitleaks ran twice, the first run succeeded with exit code 1, and the second failed with exit code 2
- **THEN** the run of Gitleaks holds two invocations in the order of the runs, with `executionSuccessful` true and `exitCode` 1, then `executionSuccessful` false and `exitCode` 2

#### Scenario: A run that timed out

- **WHEN** the record of a Gitleaks run that timed out is settled as failed
- **THEN** its invocation has `executionSuccessful` false and no `exitCode`

#### Scenario: A record that is not settled

- **WHEN** a record of Gitleaks has no success
- **THEN** the run of Gitleaks holds no invocation for it

### Requirement: The command line of an invocation is the template of its record

The `commandLine` of an invocation SHALL be the argument template of its record, with each argument but a placeholder quoted for a POSIX shell.

#### Scenario: An argument with a space

- **WHEN** the settled record of Semgrep has the template `semgrep --exclude "a b" --json {ruleset} {targets}`
- **THEN** the command line of its invocation is `semgrep --exclude 'a b' --json {ruleset} {targets}`

### Requirement: A run from scanner outcomes keeps the invocation of its outcome

A run that the outcome of a scanner gives SHALL keep the invocation of the outcome when no record of the scanner is settled.

#### Scenario: A scanner that ran, with a record that is not settled

- **WHEN** the outcome of Bandit is `ran`, and its record has no success
- **THEN** the run of Bandit holds the invocation of the outcome, with `executionSuccessful` true, and the record under `tool_runs`

### Requirement: The placeholders of the command lines are the redaction tokens of the run

A run SHALL list in `redactionTokens` each of `{targets}`, `{config}` and `{ruleset}` that a `commandLine` of the run holds, in that order. A run whose command lines hold no placeholder SHALL have no `redactionTokens`.

#### Scenario: A command line that names a config file and the targets

- **WHEN** the settled record of Gitleaks has the template `gitleaks detect --config {config} {targets}`
- **THEN** the run of Gitleaks lists `{targets}` and `{config}` in `redactionTokens`
