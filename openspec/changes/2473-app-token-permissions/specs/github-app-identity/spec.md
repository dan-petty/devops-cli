## ADDED Requirements

### Requirement: Each installation token asks only for the roadmap jobs' permissions
A process that acts as the App SHALL send the body `{"permissions": CONST_GITHUB_APP_TOKEN_PERMISSIONS}` with each exchange at `POST /app/installations/<installation_id>/access_tokens`. The constant SHALL give `issues`, `pull_requests` and `contents` the level `write`, and `checks`, `actions` and `metadata` the level `read`.

#### Scenario: The token request names the roadmap jobs' permissions
- **WHEN** the process acts as App 1001 on installation 42 and mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read"}}`

### Requirement: The log names the minted token's permissions only
After GitHub gives a token, the process SHALL log the names of the permissions in GitHub's reply, sorted, without their levels and without the token. It SHALL use the token when the reply grants more permissions than the request asks for.

#### Scenario: GitHub's reply grants one more permission
- **WHEN** GitHub's reply gives the token `ghs_first` with the six permissions and `administration: write`
- **THEN** the token is `ghs_first`, and one log record ends with `actions, administration, checks, contents, issues, metadata, pull_requests` and holds no `ghs_first`, `write` or `read`

### Requirement: A refused permission names each permission that the token asks for
When GitHub answers the exchange with HTTP 422, the `GitHubUnauthenticatedError` SHALL name each permission that the token asks for, with its level, because GitHub's reply does not say which permission the installation does not grant.

#### Scenario: The installation does not grant a permission that the token asks for
- **WHEN** GitHub answers the exchange with HTTP 422 and "The permissions requested are not granted to this installation."
- **THEN** the token lookup raises `GitHubUnauthenticatedError` whose message holds `devops-roadmap[bot]`, `HTTP 422` and `actions (read), checks (read), contents (write), issues (write), metadata (read), pull_requests (write)`
