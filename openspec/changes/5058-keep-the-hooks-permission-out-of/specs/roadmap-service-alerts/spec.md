## MODIFIED Requirements

### Requirement: The installation token reads the hooks
An installation token that names no repository, as the Service mints, SHALL ask for `repository_hooks: read` with the permissions of the roadmap jobs. A token that names one repository, as each runner Job mints, SHALL NOT ask for `repository_hooks`, because no step of a runner Job reads a hook.

#### Scenario: The token asks for the hooks
- **WHEN** the process mints an installation token of the App and `service.github_app.token_repository` is empty
- **THEN** the token request asks for `repository_hooks: read` with the permissions of the roadmap jobs

#### Scenario: The token of a runner Job does not ask for the hooks
- **WHEN** the process mints an installation token of the App and `service.github_app.token_repository` holds `example-org/app`
- **THEN** the token request asks for the permissions of the roadmap jobs and holds no `repository_hooks`
