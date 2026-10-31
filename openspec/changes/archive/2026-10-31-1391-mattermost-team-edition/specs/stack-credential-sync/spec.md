## ADDED Requirements

### Requirement: Mattermost database credential push
The cluster Secret push table SHALL declare row `mattermost/mattermost-db` under stack `chat` with secret type `kubernetes.io/basic-auth`, literal user `mattermost`, keyring password key `mattermost_db_password`, and derived connection string key `DB_CONNECTION_STRING`.

#### Scenario: Mattermost database secret attributes
- **WHEN** the cluster Secret push table is inspected
- **THEN** row `mattermost/mattermost-db` has type `kubernetes.io/basic-auth` and belongs to stack `chat`
- **AND** `DB_CONNECTION_STRING` resolves to a PostgreSQL connection URL with quoted credentials
