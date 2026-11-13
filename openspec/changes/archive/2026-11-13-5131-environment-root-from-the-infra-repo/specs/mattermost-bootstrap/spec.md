## MODIFIED Requirements

### Requirement: mattermost-bootstrap-team-and-channels
The command SHALL ensure that the specified team exists (`--team`, defaulting to the setting `mattermost.team`, whose default is `homelab`) and that public channels `alerts` and `deploys` exist in the team.

#### Scenario: Target team and channels exist
- **WHEN** team `homelab` and channels `alerts` and `deploys` already exist
- **THEN** existing IDs are reused without creating duplicates

#### Scenario: Channels missing
- **WHEN** channels `alerts` or `deploys` are missing
- **THEN** the command creates the missing channels via `mmctl --local channel create`

#### Scenario: The team of the settings
- **WHEN** `mattermost.team` is `example-team` and the command runs with `--dry-run` and no `--team`
- **THEN** the plan names the team `example-team`
