## REMOVED Requirements

### Requirement: A read-only process asks for read permissions only
**Reason**: The token of the drift Job also asks for Contents write and Administration write, because GitHub gives the merge settings and the bypass actors of a ruleset only with them (owner decision on #6875). The set, the setting and its variable are no longer read-only.
**Migration**: The requirement "The drift check asks for its own permissions" holds the set, the setting `service.github_app.drift_check` and its variable `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK`.

## ADDED Requirements

### Requirement: The drift check asks for its own permissions
When `service.github_app.drift_check` is true, each token request of the App SHALL ask for `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS` only: `administration` and `contents` with the level `write`, and each other permission of the set with `read`. The setting SHALL have the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK`, and ConfigMap `devops-cli-config` SHALL NOT carry it. A plan with this token SHALL send GET requests only.

#### Scenario: The token request of the drift check
- **WHEN** the process acts as App 1001 on installation 42, the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK` is `true`, and the process mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"actions": "read", "administration": "write", "checks": "read", "contents": "write", "environments": "read", "issues": "read", "metadata": "read", "pull_requests": "read", "secrets": "read"}}`

#### Scenario: The drift check with a write token sends only GET requests
- **WHEN** `devops repos onboard --all --plan` runs as the App with `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK` set to `true` over a repository off its baseline
- **THEN** the command exits 1, the token request asks for `administration: write` and `contents: write`, and each other request is a GET

#### Scenario: The ConfigMap leaves out the drift setting
- **WHEN** the active config sets `service.repos`, the IDs and the slug of the App and `service.github_app.drift_check`, and the ConfigMap is rendered
- **THEN** its `service.github_app` holds no `drift_check`
