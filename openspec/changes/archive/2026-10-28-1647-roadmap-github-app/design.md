# Design

## Context

`core.process` looks up the process's one GitHub token with `gh auth token` on the first GitHub call and keeps it for the life of the process. It gives the token to every gh and git child as `GH_TOKEN`. The GitHub session and the quota ledger are keyed by that token. In the cluster, Secret `devops/devops-cli` gave the token of the machine account as `GH_TOKEN`, and the Service took the machine account's login from `service.machine_account` to refuse its own webhook deliveries.

An installation token of a GitHub App expires after one hour, cannot read `GET /user`, and changes each time the App mints one.

## Goals / Non-Goals

**Goals:**

- The Service and the cluster Jobs act as GitHub App `devops-roadmap`, with an installation token that the process renews before it expires.
- A workstation keeps the gh login of its person.
- The ledger, the session, the login, the commit identity and the webhook filter follow the App.
- The cluster Secret, the ConfigMap and `devops k8s push-secrets` carry the App's settings and key, and nothing of the machine account stays.

**Non-Goals:**

- Move the repositories or the board to an organization.
- Change how the roadmap store reads or writes the board. A separate item moves the roadmap state to labels and milestones.
- Raise `replicas` of `deployment/roadmap-service`, or replace the webhooks of each repository with the App's webhook.

## Decisions

- **Decision: the private key in the environment selects the App.**
  *Choice:* `core.process.acts_as_github_app()` is true when the environment holds `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`. Secret `devops/devops-cli` gives it to the pods through `envFrom`.
  *Rejected alternative:* act as the App when `service.github_app` is set.
  *Evidence for rejection:* the workstation holds `service.github_app` to render the ConfigMap (`render_active_devops_configmap` reads `config.yaml`) and holds the key in its keyring for the push, so it would act as the bot. The owner wants the workstation on the gh login of its person.
  *Rejected alternative:* a new setting that turns the App on.
  *Evidence for rejection:* the Secret already reaches only the pods, so a second switch adds a value that can disagree with the key.
  *Rejected alternative:* use the App when `gh auth token` gives no token.
  *Evidence for rejection:* a workstation whose gh login expired would act as the bot and give no warning.
- **Decision: renew the token when less than `DEFAULT_GITHUB_APP_TOKEN_RENEW_SECONDS` (600 s) are left.**
  *Choice:* `core.process` keeps the token with its `expires_at` and mints a new one on the first call after the renewal time.
  *Rejected alternative:* mint a new token only after GitHub answers 401.
  *Evidence for rejection:* a gh child or a git push that starts with a token that expires during its run fails, and GitHub gives `expires_at`, so the time is known.
  *Rejected alternative:* mint one token for each request.
  *Evidence for rejection:* each mint is one more request, and it puts the App's JWT in use for each call.
- **Decision: the identity keys the session and the ledger, and the session reads the current token for each request.**
  *Choice:* `GitHubIdentity(key, login)`. The key is gh's token for a gh login, and `app-installation-<installation_id>` for the App. `SessionGitHubAPI._request` paces each attempt on the ledger, then reads `github_token()` and sends it.
  *Rejected alternative:* replace the session when the token changes, as before.
  *Evidence for rejection:* `get_github_session()` closes the replaced session's transport, so a listing in progress, in the same thread or in the other lane of the Service, fails with `unread_after_close` once an hour. A ledger keyed by the token also starts empty for each new token, and its first pacing would ask gh for the quota.
- **Decision: the login comes from `service.github_app.slug`.**
  *Choice:* `GitHubSession.login` returns `<slug>[bot]` and sends no request.
  *Rejected alternative:* read the slug from `GET /app` with the JWT.
  *Evidence for rejection:* the webhook filter needs the login when the Service starts, before any request, and the issue asks for the login from settings.
- **Decision: the commit email takes the account ID from `GET /users/<login>`, for both identities.**
  *Choice:* `GitHubSession.commit_email` is `<id>+<login>@users.noreply.github.com`.
  *Rejected alternative:* a setting for the bot's user ID.
  *Evidence for rejection:* it is one more value to type and to keep equal to GitHub's.
  *Rejected alternative:* keep `<login>@users.noreply.github.com` for a person and add the ID only for the App.
  *Evidence for rejection:* that is two rules for one email, and GitHub gives the form with the ID to each account.
- **Decision: the ConfigMap renderer reads and writes YAML.**
  *Choice:* PyYAML loads the template's config, sets `service` to the repositories, the App and the timings, validates it as `Settings`, and writes it again.
  *Rejected alternative:* extend the regular expression that replaced `machine_account`.
  *Evidence for rejection:* the App is a nested block of three keys, and the project uses a parser for a structured format. The applied ConfigMap loses the template's comments, which the template in the repository keeps.
- **Decision: the webhook status is `ignored_own_write`.**
  *Choice:* `CONST_SERVICE_STATUS_OWN_WRITE`.
  *Rejected alternative:* keep `ignored_machine_account`.
  *Evidence for rejection:* no machine account remains, and the issue asks that no `machine_account` name stays in `src/`.
