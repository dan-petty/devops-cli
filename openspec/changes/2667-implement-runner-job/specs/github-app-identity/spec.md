# Spec Delta

## ADDED Requirements

### Requirement: A Job's installation token names one repository
When the setting `service.github_app.token_repository` holds `owner/name`, the installation token request SHALL send `repositories` with the one entry `name` besides the permissions. With the setting empty, the request SHALL send no `repositories`. The setting SHALL have the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY`, and a value that is not `owner/name` SHALL be refused.

#### Scenario: A runner Job
- **WHEN** the setting holds `example/project` and the process mints a token
- **THEN** the request body is `{"permissions": {...}, "repositories": ["project"]}`

#### Scenario: The Service
- **WHEN** the setting is empty and the process mints a token
- **THEN** the request body holds `permissions` and no `repositories`

#### Scenario: A bad value
- **WHEN** the setting holds `project`
- **THEN** the settings refuse it
