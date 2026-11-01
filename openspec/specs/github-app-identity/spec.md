# github-app-identity Specification

## Purpose
How a devops-cli process acts as the roadmap's GitHub App: when it acts as the App, how it mints and renews the App's installation token, which login and ledger it uses, and how the roadmap Service, its webhook consumer, the cluster ConfigMap and the cluster Secret carry the App.

## Requirements

### Requirement: The private key in the environment makes the process act as the App
A process whose environment holds `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` SHALL act as the GitHub App that `service.github_app.app_id`, `service.github_app.installation_id` and `service.github_app.slug` name. A process without the key in its environment SHALL act as gh's login, from `gh auth token`, also when the App's settings are set. A process with the key and an App setting that is not set SHALL raise `ConfigurationError` naming each setting that is not set.

#### Scenario: A workstation holds the App's settings but not its key in the environment
- **WHEN** `service.github_app` names App 1001, installation 42 and slug `devops-roadmap`, the environment holds no `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and the session's login is read
- **THEN** the session sends `GET /user` and sends no request to `/app/installations/42/access_tokens`

#### Scenario: The key is in the environment and an App setting is not set
- **WHEN** the environment holds the key, `service.github_app` sets only the slug, and the process asks for its token
- **THEN** it raises `ConfigurationError` whose message names `service.github_app.app_id` and `service.github_app.installation_id`

### Requirement: The App mints an installation token and renews it before it expires
A process that acts as the App SHALL sign a JWT whose issuer is the App ID with the private key, and SHALL exchange it at `POST /app/installations/<installation_id>/access_tokens` for an installation token. It SHALL keep the token until less than `DEFAULT_GITHUB_APP_TOKEN_RENEW_SECONDS` are left before GitHub's `expires_at`, and SHALL then mint a new one on the next call. Each gh and git child SHALL get the current token as `GH_TOKEN`.

#### Scenario: A token near its expiry is renewed for the next gh child
- **WHEN** the first exchange gives `ghs_first`, which expires in 5 minutes, the second gives `ghs_second`, which expires in one hour, and three gh children start one after another
- **THEN** the children get `ghs_first`, `ghs_second` and `ghs_second`, GitHub receives two exchanges, and the first exchange carries a bearer JWT whose `iss` is `1001`

### Requirement: A failed exchange names the App and the reason
A refused exchange, or a key that cannot sign a JWT, SHALL raise `GitHubUnauthenticatedError` that names the App's bot login and the reason. For a refused exchange with HTTP 401, the reason SHALL include GitHub's message from the response body and SHALL NOT include `gh auth login` or `GH_TOKEN`. The error SHALL never hold the key.

#### Scenario: GitHub refuses the exchange
- **WHEN** GitHub answers the exchange with HTTP 401 and body `{"message": "A JSON web token could not be decoded"}`
- **THEN** the token lookup raises `GitHubUnauthenticatedError` whose message holds `devops-roadmap[bot]`, `POST /app/installations/42/access_tokens`, `401`, `A JSON web token could not be decoded`, and `Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and does not hold `gh auth login` or `GH_TOKEN`

#### Scenario: The key is no RSA key
- **WHEN** the environment holds `not-a-pem-key` as the key
- **THEN** the token lookup raises `GitHubUnauthenticatedError` that says the key is not an RSA private key in PEM form, does not quote the key, and sends no request

### Requirement: The App's identity is its installation and its bot login
A process that acts as the App SHALL use `<slug>[bot]` as its login with no request. The quota ledger and the GitHub session SHALL be keyed by the installation, so a new installation token keeps the same ledger and the same session, and the session SHALL send each request with the current token.

#### Scenario: The login is read
- **WHEN** a process that acts as App `devops-roadmap` reads its session's login
- **THEN** the login is `devops-roadmap[bot]` and the process sends no request

#### Scenario: Two tokens of one installation read through one session
- **WHEN** the session sends two GETs, and the token is renewed between them
- **THEN** the GETs carry `token ghs_first` and `token ghs_second`, the session is the same object, and one ledger holds the quota that the second answer reports

### Requirement: The job clone commits as the identity's account
The job clone SHALL set `user.name` to the session's login and `user.email` to `<id>+<login>@users.noreply.github.com`, where `GET /users/<login>` gives the ID.

#### Scenario: The App's bot commits
- **WHEN** GitHub answers `GET /users/devops-roadmap%5Bbot%5D` with ID 7, and the session's commit email is read
- **THEN** the email is `7+devops-roadmap[bot]@users.noreply.github.com`

#### Scenario: A person's login commits
- **WHEN** `GET /user` gives `test-bot`, `GET /users/test-bot` gives ID 4242, and the job clone is checked out
- **THEN** the clone's `user.name` is `test-bot` and its `user.email` is `4242+test-bot@users.noreply.github.com`

### Requirement: The roadmap's webhook consumer refuses the App bot's own writes
The roadmap's webhook consumer SHALL refuse a delivery whose sender's login is the App's bot login, compared without case, and the router SHALL answer it with HTTP 200 and status `ignored_own_write`. A delivery from another sender SHALL start a round.

#### Scenario: The bot's event comes back as a webhook
- **WHEN** a signed `issues` delivery arrives whose sender is `BOT-ACCOUNT[bot]` and the App's slug is `bot-account`
- **THEN** the answer is HTTP 200 with `{"status": "ignored_own_write"}` and neither lane runs a round

#### Scenario: A person's event arrives
- **WHEN** a signed `issues` delivery arrives whose sender is `human-user`
- **THEN** the answer is HTTP 202

### Requirement: The Service starts only as the App
`devops serve --service` SHALL exit with status 1 and name each App setting that is not set, and SHALL exit with status 1 and name `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and the bot login when the environment does not hold the key.

#### Scenario: The App's settings are not set
- **WHEN** `devops serve --service` runs with `service.repos` set and no App setting
- **THEN** it exits with status 1, and the output names `service.github_app.app_id`, `service.github_app.installation_id` and `service.github_app.slug`

#### Scenario: The key is not in the environment
- **WHEN** `devops serve --service` runs with the App's settings and no key in the environment
- **THEN** it exits with status 1, and the output names `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `devops-roadmap[bot]`

### Requirement: The cluster Secret and the ConfigMap carry the App
Secret `devops/devops-cli` SHALL hold `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` from keyring `service_github_app_private_key` and SHALL hold no `GH_TOKEN`. `devops k8s push-secrets` SHALL run no gh command. ConfigMap `devops-cli-config` SHALL hold `service.github_app` with the App ID, the installation ID and the slug, and a deploy SHALL refuse to render it when one of them is not set, naming each.

#### Scenario: The dry run of the devops Secret
- **WHEN** `devops k8s push-secrets --only devops/devops-cli --dry-run` lists its requests
- **THEN** it lists the keyring read `devops-cli/service_github_app_private_key` and the entry `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` as `<base64 of keyring service_github_app_private_key>`, with no `GH_TOKEN`, no gh request and no value

#### Scenario: A push of the devops stack
- **WHEN** the keyring holds the App's key and `devops k8s push-secrets --stack devops` runs
- **THEN** the live Secret holds the key under `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, and no gh child runs

#### Scenario: The ConfigMap without the App's IDs
- **WHEN** the active config sets `service.repos` and only `service.github_app.slug`, and the ConfigMap is rendered
- **THEN** the render raises `KubernetesContextError` naming `service.github_app.app_id` and `service.github_app.installation_id`

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

### Requirement: A delivery of the App bot's own write counts as self
The router SHALL count a delivery that the roadmap consumer refuses as the App bot's own write in `devops_cli_service_webhook_deliveries_total` with the outcome `self`, apart from the other ignored deliveries, and SHALL still answer it with HTTP 200 and status `ignored_own_write`.

#### Scenario: The bot's write and a repeated delivery
- **WHEN** a signed `issues` delivery arrives twice with one delivery id, and another arrives whose sender is the App's bot
- **THEN** the counter has one `issues` delivery with the outcome `ignored` and one with the outcome `self`

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
