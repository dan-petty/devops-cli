## MODIFIED Requirements

### Requirement: The SARIF run of a review tool holds the records of that tool

The SARIF document of a review SHALL hold each `ToolRun` record of a tool in the property bag of the run of that tool, under `tool_runs`, with the field names of `ToolRun` and in the order of the runs. The run SHALL hold no `artifacts` from a record. The run SHALL hold one `versionControlProvenance` entry, with `repositoryUri` and `revisionId`, for each distinct pair of `repository_uri` and `commit` among the records of the tool whose `repository_uri` is set and whose `commit` is set and does not end with `-dirty`, in the order of the first record of each pair. The run SHALL hold no `versionControlProvenance` when no record has such a pair. The document SHALL validate against the SARIF 2.1.0 JSON schema.

#### Scenario: A tool that gave a result

- **WHEN** a review writes `findings.sarif`, and Gitleaks ran twice and gave one result, and no record of Gitleaks has a `repository_uri`
- **THEN** the run of Gitleaks holds the two records of Gitleaks under `tool_runs`, and `ToolRun` reads each one back with no change
- **AND** the run holds no `artifacts` and no `versionControlProvenance`
- **AND** the document validates against the SARIF 2.1.0 JSON schema

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
