## ADDED Requirements

### Requirement: versionControlProvenance in SARIF export
The SARIF export SHALL write versionControlProvenance with repositoryUri and revisionId when the ToolRun has a repository_uri and a commit that does not end with -dirty, and SHALL write no versionControlProvenance otherwise.

#### Scenario: Clean commit with repository
- **WHEN** a ToolRun has repository_uri set and commit does not end with -dirty
- **THEN** the SARIF run has versionControlProvenance with repositoryUri and revisionId

#### Scenario: Dirty commit
- **WHEN** a ToolRun has repository_uri set and commit ends with -dirty
- **THEN** the SARIF run has no versionControlProvenance

#### Scenario: No repository
- **WHEN** a ToolRun has repository_uri None
- **THEN** the SARIF run has no versionControlProvenance
