## MODIFIED Requirements

### Requirement: Each installation token asks only for the roadmap jobs' permissions
Each token request of the App at `POST /app/installations/<installation_id>/access_tokens` SHALL ask for `CONST_GITHUB_APP_TOKEN_PERMISSIONS`: `issues`, `pull_requests`, `contents` and `workflows` with the level `write`, and `checks`, `actions` and `metadata` with the level `read`. When `service.github_app.token_repository` is empty, it SHALL also ask for `CONST_GITHUB_APP_METRICS_TOKEN_PERMISSIONS`: `repository_hooks` and `administration` with the level `read`. When `service.github_app.read_only` is true, the request SHALL ask for `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` only: `actions`, `administration`, `checks`, `contents`, `environments`, `issues`, `metadata`, `pull_requests` and `secrets` with the level `read`. The setting SHALL have the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_READ_ONLY`, and ConfigMap `devops-cli-config` SHALL NOT carry it.

#### Scenario: The token request names the roadmap jobs' permissions
- **WHEN** the process acts as App 1001 on installation 42, `service.github_app.token_repository` is empty, and the process mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read", "workflows": "write", "repository_hooks": "read", "administration": "read"}}`

#### Scenario: The token request of a runner Job
- **WHEN** the process acts as App 1001 on installation 42, `service.github_app.token_repository` holds `example-org/app`, and the process mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read", "workflows": "write"}, "repositories": ["app"]}`, with no `repository_hooks` and no `administration`

#### Scenario: The token request of a read-only process
- **WHEN** the process acts as App 1001 on installation 42, the variable `DEVOPS_CLI_SERVICE_GITHUB_APP_READ_ONLY` is `true`, and the process mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"actions": "read", "administration": "read", "checks": "read", "contents": "read", "environments": "read", "issues": "read", "metadata": "read", "pull_requests": "read", "secrets": "read"}}`, with no level `write`

#### Scenario: The ConfigMap leaves out the read-only setting
- **WHEN** the active config sets `service.repos`, the IDs and the slug of the App and `service.github_app.read_only`, and the ConfigMap is rendered
- **THEN** its `service.github_app` holds no `read_only`
