## ADDED Requirements

### Requirement: A plan correction passes the file rule
The plan file rule SHALL accept a pull request whose title names the issue and that adds, modifies, renames or copies a file in `openspec/changes/<issue>-<slug>/`. A pull request that only removes a file of that folder SHALL still take the blocker.

#### Scenario: A correction of a merged plan
- **WHEN** a plan pull request changes `openspec/changes/<issue>-<slug>/proposal.md` with status `modified`
- **THEN** the file rule reports no blocker

#### Scenario: A removal alone
- **WHEN** the pull request only removes a file of the folder
- **THEN** the file rule reports one blocker

#### Scenario: No file of the folder
- **WHEN** the pull request changes no file of the folder
- **THEN** the file rule reports one blocker that names the folder
