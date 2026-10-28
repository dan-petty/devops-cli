# Roadmap jobs act as a GitHub App on the personal account

ADR 0015 supersedes [ADR 0002](0002-roadmap-jobs-act-as-a-machine-account.md).

ADR 0002 gave the roadmap jobs a machine account with a classic token, because only a classic token can reach a project board that a personal account owns. GitHub suspended that machine account on 2026-10-11 ([#1562](https://github.com/dan-petty/devops-cli/issues/1562)). Since then, no roadmap job can call GitHub without a person, and `deployment/roadmap-service` stays at `replicas: 0`.

On 2026-10-28 the owner decided that the repositories and the board stay on the personal account, and that no organization is made. The owner also said: "roadmap should perform all expected functionality even if project board is unavailable for the repository".

## Decision

- **The jobs act as a GitHub App.** The personal account owns the App `devops-roadmap` and installs it on its managed repositories. The App has these repository permissions: Issues read and write, Pull requests read and write, Contents read and write, Checks read, Actions read and Metadata read. It has no webhook and no user authorization.
- **The private key selects the App.** A process whose environment holds the App's private key, `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, acts as the App. Secret `devops/devops-cli` gives the key to the Service and to each cluster Job. A workstation keeps the key only in the OS keyring, for `devops k8s push-secrets`, so a workstation run keeps the gh login of its person. gh applies the same rule to `GH_TOKEN`: a token in the environment takes precedence over a stored login.
- **gidgethub mints the token.** The process signs a JWT with the key and exchanges it for an installation token with `gidgethub.apps.get_installation_access_token`. An installation token expires one hour after GitHub makes it, and the process mints a new one when less than ten minutes are left. Each gh and git child gets the current token as `GH_TOKEN`. git gets it through `gh auth git-credential`.
- **The installation is the identity.** The quota ledger and the GitHub session are keyed by the installation, so each new token keeps them. The session reads the current token for each request.
- **The login is the bot's.** An installation token cannot read `GET /user`, so the login is `<slug>[bot]`, from `service.github_app.slug`. The job clone commits as that login, with the email `<id>+<login>@users.noreply.github.com`. The ID comes from `GET /users/<login>`. The roadmap's webhook consumer refuses a delivery whose sender is that login.
- **The settings.** `service.github_app.app_id`, `service.github_app.installation_id` and `service.github_app.slug` go into ConfigMap `devops-cli-config`. The private key is the managed credential `service.github_app.private_key`, which a person stores with `devops config set --from-file`. The settings `service.machine_account` and `k8s.github_account` are removed.

## Considered Options

- **Move the repositories and the board to an organization**: rejected by the owner. An App can reach a board only through the organization permission "Projects", but the move is hard to undo and changes the repository and image paths.
- **A new machine account with a classic token**: rejected. GitHub suspended the last one, and a classic token reaches every repository of its account.
- **A fine-grained personal access token**: rejected. It has no permission for the board of a personal account either, and it acts as a person, so the roadmap cannot tell its own writes from the person's.
- **Select the App from its settings alone**: rejected. A workstation holds the App's settings to render the ConfigMap, so it would act as the App instead of as its person.
- **Fall back to the App when gh has no login**: rejected. A workstation whose gh login expired would act as the bot and give no warning.

## Consequences

- An installation token cannot read or write the project board of a personal account, because GitHub gives Apps the "Projects" permission only for an organization. A separate item moves the roadmap state to labels and milestones, so that the roadmap works without the board. `deployment/roadmap-service` stays at `replicas: 0` until that item merges.
- The App's private key is in Secret `devops/devops-cli`. It is narrower than the classic token it replaces: it reaches only the installed repositories with the granted permissions, and each token that it mints expires after one hour.
- The App's writes show as `devops-roadmap[bot]`, so a person can tell them from their own writes.
- The webhooks of each repository stay. The App's own webhook can replace them in a later item.
