# Proposal

## Why

Issue #1647: GitHub suspended the machine account of the roadmap Service on 2026-10-11 (#1562). The Service and every cluster Job read the classic token of that account from Secret `devops/devops-cli` as `GH_TOKEN`, so no roadmap job can call GitHub without a person, and `deployment/roadmap-service` stays at `replicas: 0`.

The owner changed the scope of the item on 2026-10-28. The repositories and the board stay on the personal account, and nobody makes an organization. The Service acts as a GitHub App, `devops-roadmap`, which the personal account owns and installs on its repositories. A workstation run of `devops` keeps the gh login of its person.

## What Changes

- A process whose environment holds the App's private key (`DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`) acts as the App. It signs a JWT with the key and exchanges it for an installation token through `gidgethub.apps.get_installation_access_token`. It mints a new token before the token expires. Each gh and git child gets the current token as `GH_TOKEN` through the existing pin. Without the key in the environment, the process acts as gh's login, as before.
- The App's login is `<slug>[bot]`, from settings, and the session sends no `GET /user` for it. The job clone commits as the login with the email `<id>+<login>@users.noreply.github.com`, where `GET /users/<login>` gives the ID. A person's clone uses the same form.
- The identity keys the quota ledger and the GitHub session: the installation for the App, the token for a gh login. A new installation token keeps the ledger and the session, and the session reads the current token for each request.
- New settings `service.github_app.app_id`, `service.github_app.installation_id` and `service.github_app.slug` go into ConfigMap `devops-cli-config`. The new managed credential `service.github_app.private_key` (keyring `service_github_app_private_key`) is stored with `devops config set --from-file` and written by `devops k8s push-secrets` to Secret `devops/devops-cli` as `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`.
- Removed with no alias: `service.machine_account`, `k8s.github_account`, the `GH_TOKEN` row of the Secret table and its `GitHubAccountSource`, the gh account read of `push-secrets`, its `--github-account` option and its dry-run requests.
- The roadmap's webhook consumer refuses a delivery whose sender is the App's bot, with status `ignored_own_write`. `devops serve --service` does not start without the App's settings and its key in the environment.
- ADR 0015 supersedes ADR 0002. `k8s/README.md`, the ConfigMap template, the comment of the Deployment, ADR 0004, ADR 0009 and the knowledge base describe the App.
- A command, settings, a manifest and the behavior of the Service change, so the change has a spec delta: the new capability `github-app-identity`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `github-app-identity`: how a process acts as the roadmap's GitHub App, how it mints and renews its installation token, and how the Service, its webhook consumer, the ConfigMap and the cluster Secret carry the App.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/core/process.py`, `src/devops_cli/github/app_installation.py` (new), `github/session.py`, `github/session_transport.py`, `github/rate_limiter.py`.
- `src/devops_cli/config/settings.py`, `config/options.py`, `config/env.py`, `config/constants.py`, `config/defaults.py`, `security/secrets.py`, `commands/config.py`.
- `src/devops_cli/k8s/cluster_secrets.py`, `k8s/secret_push.py`, `k8s/configmap.py`, `commands/k8s/cluster_secret_push.py`, `lang/en/`.
- `src/devops_cli/server/routes/webhooks.py`, `server/service.py`, `commands/serve.py`, `roadmap/run.py`.
- `k8s/devops/configmap.example.yaml`, `k8s/devops/roadmap-service/deployment.yaml` (comment only; `replicas` stays 0), `k8s/README.md`, `config.example.yaml`, `docs/adr/`.
- The roadmap store keeps its board reads and writes. An installation token cannot reach the board of a personal account, so a board call fails until a separate item moves the roadmap state to labels and milestones.

## Feasibility

Checked on 2026-10-28:

- The pinned gidgethub 6.0.0, read with `inspect.getsource(gidgethub.apps)` in the project environment, has `get_jwt(*, app_id, private_key, expiration=600)`, which signs RS256 through PyJWT 2.15.1 and cryptography 50.0.2. It also has `get_installation_access_token(gh, *, installation_id, app_id, private_key)`, which sends `POST /app/installations/{installation_id}/access_tokens` with the JWT and returns GitHub's `token` and `expires_at`.
- `gh help environment` of gh 2.103.2 (the image pins 2.102.1) says that `GH_TOKEN` is "an authentication token that will be used when a command targets either `github.com` or a subdomain of `ghe.com`" and that it "takes precedence over previously stored credentials". gh does not check the kind of token: the `GITHUB_TOKEN` of GitHub Actions is an installation access token, and GitHub's documentation gives it to gh as `GH_TOKEN`. The image's git asks `gh auth git-credential`, which gives git the same token.
- GitHub's REST reference, "Create an installation access token for an app": the token expires one hour after GitHub makes it.
- `uv run devops gh api users/dan-petty --jq .type` prints `User`. GitHub's "Permissions required for GitHub Apps" lists "Projects" only under organization permissions, so an installation token of an App on a personal account cannot read or write board 12 (`.github/roadmap.toml`). GitHub's "Installing your own GitHub App" says that a private App can be installed on the account that owns it. The repository permissions (Issues, Pull requests, Contents, Checks, Actions, Metadata) apply to the repositories of a user.
- An installation token cannot read `GET /user`, which needs a user, so the App's login comes from settings. The README of `actions/create-github-app-token` sets the commit email of a bot to `<user-id>+<app-slug>[bot]@users.noreply.github.com`, with the ID from `GET /users/<app-slug>[bot]`.
- The premise holds for the identity. The board part of the roadmap does not work with an App, and the owner moved that work to a separate item. This change does not touch the store or the job code for the board.

## Existing Tool Considered

gidgethub, pinned at 6.0.0 and already the client of the GitHub session (ADR 0006), mints the JWT and the installation token with `gidgethub.apps`. gh and git use the token through gh's own `GH_TOKEN` and `gh auth git-credential`. GitHub's App installation replaces the machine account. The change builds no JWT, HTTP or credential-helper code. It adds only the renewal time and the selection of the identity.

The change deletes `GitHubAccountSource`, `read_github_account_token` and the rest of the gh account read of `devops k8s push-secrets`, with its `--github-account` option and its dry-run requests. It deletes the settings `service.machine_account` and `k8s.github_account`, and the regular expression that replaced the service block of the ConfigMap, which PyYAML now reads and writes.
