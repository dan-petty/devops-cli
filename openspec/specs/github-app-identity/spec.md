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
A refused exchange, or a key that cannot sign a JWT, SHALL raise `GitHubUnauthenticatedError` that names the App's bot login and the reason. The error SHALL never hold the key.

#### Scenario: GitHub refuses the exchange
- **WHEN** GitHub answers the exchange with HTTP 401
- **THEN** the token lookup raises `GitHubUnauthenticatedError` whose message holds `devops-roadmap[bot]` and `401`

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
