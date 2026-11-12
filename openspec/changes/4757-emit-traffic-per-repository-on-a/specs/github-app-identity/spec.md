## MODIFIED Requirements

### Requirement: Each installation token asks only for the roadmap jobs' permissions
A process that acts as the App SHALL send the body `{"permissions": CONST_GITHUB_APP_TOKEN_PERMISSIONS}` with each exchange at `POST /app/installations/<installation_id>/access_tokens`. The constant SHALL give `issues`, `pull_requests`, `contents` and `workflows` the level `write`, and `checks`, `actions`, `metadata` and `administration` the level `read`.

#### Scenario: The token request names the roadmap jobs' permissions
- **WHEN** the process acts as App 1001 on installation 42 and mints a token
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read", "workflows": "write", "administration": "read"}}`
