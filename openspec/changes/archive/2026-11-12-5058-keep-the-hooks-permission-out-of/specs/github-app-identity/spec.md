## MODIFIED Requirements

### Requirement: Each installation token asks only for the roadmap jobs' permissions
Each token request of the App at `POST /app/installations/<installation_id>/access_tokens` SHALL ask for `CONST_GITHUB_APP_TOKEN_PERMISSIONS`: `issues`, `pull_requests`, `contents` and `workflows` with the level `write`, and `checks`, `actions` and `metadata` with the level `read`. When `service.github_app.token_repository` is empty, it SHALL also ask for `CONST_GITHUB_APP_METRICS_TOKEN_PERMISSIONS`: `repository_hooks` and `administration` with the level `read`.

#### Scenario: The token request names the roadmap jobs' permissions
- **WHEN** the process acts as App 1001 on installation 42, `service.github_app.token_repository` is empty, and the process mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read", "workflows": "write", "repository_hooks": "read", "administration": "read"}}`

#### Scenario: The token request of a runner Job
- **WHEN** the process acts as App 1001 on installation 42, `service.github_app.token_repository` holds `example-org/app`, and the process mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read", "workflows": "write"}, "repositories": ["app"]}`, with no `repository_hooks` and no `administration`

### Requirement: A refused permission names each permission that the token asks for
When GitHub answers the exchange with HTTP 422, the `GitHubUnauthenticatedError` SHALL name each permission that the token of this process asks for, with its level, because GitHub's reply does not say which permission the installation does not grant.

#### Scenario: The installation does not grant a permission that the token asks for
- **WHEN** `service.github_app.token_repository` is empty and GitHub answers the exchange with HTTP 422 and "The permissions requested are not granted to this installation."
- **THEN** the token lookup raises `GitHubUnauthenticatedError` whose message holds `devops-roadmap[bot]`, `HTTP 422` and `actions (read), administration (read), checks (read), contents (write), issues (write), metadata (read), pull_requests (write), repository_hooks (read), workflows (write)`

#### Scenario: The installation does not include the repository of a runner Job
- **WHEN** `service.github_app.token_repository` holds `example-org/app` and GitHub answers the exchange with HTTP 422
- **THEN** the message names the repository `example-org/app` and each permission of the token, and holds no `repository_hooks` and no `administration`
