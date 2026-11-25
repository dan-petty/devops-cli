## MODIFIED Requirements

### Requirement: Each installation token asks only for the roadmap jobs' permissions
Unless `read_only` or a phase scope overrides it, `POST /app/installations/<installation_id>/access_tokens` SHALL request `CONST_GITHUB_APP_TOKEN_PERMISSIONS` (`issues`, `pull_requests`, `contents`, `workflows` write; `checks`, `actions`, `metadata` read), plus `CONST_GITHUB_APP_METRICS_TOKEN_PERMISSIONS` when `token_repository` is empty.

#### Scenario: The token request names the roadmap jobs' permissions
- **WHEN** the process acts as App 1001 on installation 42, `service.github_app.token_repository` is empty, and the process mints a token outside a phase scope
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read", "workflows": "write", "repository_hooks": "read", "administration": "read"}}`

#### Scenario: The token request of a runner Job
- **WHEN** the process acts as App 1001 on installation 42, `service.github_app.token_repository` holds `example-org/app`, and the process mints a token outside a phase scope
- **THEN** the body of `POST /app/installations/42/access_tokens` is `{"permissions": {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read", "workflows": "write"}, "repositories": ["app"]}`, with no `repository_hooks` and no `administration`

## ADDED Requirements

### Requirement: Prepare token holds the permissions of the prepare phase
The installation token of each `prepare` phase SHALL request `contents: read`, `pull_requests: read`, `issues: write`, `checks: read` and `actions: read`, and SHALL NOT request `workflows`.

#### Scenario: Prepare phase token request
- **WHEN** the test builds the token request of the `prepare` phase with a fake GitHub client
- **THEN** the requested permissions equal `contents: read`, `pull_requests: read`, `issues: write`, `checks: read` and `actions: read`, and hold no `workflows` key

### Requirement: Publish token omits workflows write for a plan with no workflow file
The `publish` phase SHALL NOT request `workflows: write` when the merged plan names no workflow file.

#### Scenario: Publish token for a plan with no workflow file
- **WHEN** the test builds the token request of `publish` for a merged plan that names no file under `.github/workflows/`
- **THEN** the requested permissions hold no `workflows` key, and `contents` and `pull_requests` stay `write`

### Requirement: Publish token asks workflows write for a workflow file
The `publish` phase MUST request `workflows: write` when the merged plan names a workflow file.

#### Scenario: Publish token for a plan with a workflow file
- **WHEN** the test builds the token request of `publish` for a merged plan that names `.github/workflows/ci.yml`
- **THEN** the requested permissions hold `workflows: write`

### Requirement: ADR 0030 has no deferred token sentence
ADR 0030 SHALL hold no `Until #3700` sentence about the token.

#### Scenario: ADR 0030 text
- **WHEN** `rg -n 'Until #3700.*token|token keeps.*workflows: write' docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md` runs
- **THEN** it prints no match
