# Proposal: #6783

## Why
Closes #6783. `devops repos onboard --all --plan` gives each pending change of the repositories of `service.repos` ([ADR 0035](../../../docs/adr/0035-the-onboard-command-owns-the-repository-settings.md), #6773). Nothing runs it on a schedule, so a setting that a person changes in the web UI stays off the baseline until somebody runs the command. ADR 0035 (Confirmation) names a nightly drift Job that runs the command.

## What Changes
- A new CronJob `repos-drift` in `k8s/devops/` runs `devops repos onboard --all --plan` each night in the runner image. Its pod acts as the GitHub App of the Service with an installation token that has read permissions only. It mounts no ServiceAccount token, and its ServiceAccount has no Role.
- The setting `service.github_app.read_only` (variable `DEVOPS_CLI_SERVICE_GITHUB_APP_READ_ONLY`) makes the token request ask for `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` only. The ConfigMap does not carry the setting.
- Row 0 sends no `GET /user` when the process acts as the App: GitHub refuses that request to an installation token, and before this change the error stopped the whole run.
- `--all --plan` sets the new gauge `devops_cli_repos_drift_rows` for each repository, with the label `state`: `drift` counts the rows off the baseline (`pending`, `failed`, `waiting`), and `not_readable` counts the rows that the check could not read. After the reports, the command prints one line for each repository: `drift`, `not readable` or `clean`.
- The new rule group `repos-drift` holds three warning alerts: `RepositorySettingsDrift`, `RepositorySettingsUnreadable` and `RepositoryDriftCheckStopped`. The alert table of `k8s/README.md` gives the action of each.
- The command, a manifest and the alert rules are observable, so the change carries spec deltas: `repos-onboard`, `github-app-identity` and the new capability `repos-drift-alerts`.
- The change fits one pull request.

## Capabilities
- `repos-onboard`: ADDED requirements "The drift check reports the state of each repository" and "The drift check prints the state of each repository". MODIFIED requirement "The preflight stops a confirm", because an installation token has no OAuth scopes and GitHub refuses it `GET /user`.
- `github-app-identity`: MODIFIED requirement "Each installation token asks only for the roadmap jobs' permissions", because a read-only process asks for the read set instead.
- `repos-drift-alerts` (new): the nightly Job and its three alerts.

## Impact
- A setting of a repository that drifts from the baseline gives a warning alert within one day. A row that the Job cannot read gives its own warning alert, not a drift alert and not a clean state.
- Until the runner image holds the `copier` program (dan-petty/devtools pull request 43), the rows that read the baseline are `not readable`, so `RepositorySettingsUnreadable` fires for each repository each night. The alert names the rows, and its runbook row gives the reason.
- The Job reads GitHub only. It sends no write, files no issue and changes no cluster object.
- The deploy is a person step: the change applies no manifest.

## Feasibility
- Command: `src/devops_cli/commands/repos.py` on origin/main `019753720` runs each target of `service.repos` with `--all` and exits 1 when a report is `failing`. `OnboardReport.failing` (`src/devops_cli/github/onboard/model.py`) counts `pending`, `failed`, `not readable` and, in a plan, `waiting`.
- Identity: `GitHubApp.permissions` (`src/devops_cli/github/app_installation.py`) already replaces the permissions of the token request, and `_exchange` sends them as the body of `POST /app/installations/<id>/access_tokens`. ADR 0015 says that the owner gave the App read and write on each repository permission, so the installation grants each permission of the read set.
- The App and `GET /user`: the docstring of `app_installation.py` says that an installation token cannot read `GET /user`. `token_scopes` in `src/devops_cli/github/onboard/settings_rows.py` sends `GET /user` before the guarded rows, and raises `DevOpsCLIError` on any status but 200, so a run as the App stops before row 0.
- Permissions: the page "Permissions required for GitHub Apps" (docs.github.com, read 2026-11-22) puts the GETs of the plan under Administration (vulnerability alerts, immutable releases, CodeQL default setup, workflow permissions), Metadata (rulesets, private vulnerability reporting), Actions (environments, branch policies), Environments (environment variables and secrets), Secrets (`/actions/secrets`), Issues (labels), Contents, Pull requests and Checks, each with the level read. It puts `GET /repos/{owner}/{repo}/code-quality/setup` under Administration with the level write, so the read token cannot read row 4.
- Image: the `runner` stage of `Dockerfile` is `FROM devtools`. `devops gh api repos/dan-petty/devtools/pulls/43` gives "feat(image): add the copier program", state open, not merged. `render_baseline` raises `BaselineUnreadableError` with a person step when `copier` is not on PATH, and the guarded rows read `not readable`.
- Report pattern: the SRE guideline (`docs/guidelines/sre.md`, Alerts and routing) makes a cause a ticket, a warning alert with a runbook row, and Alertmanager routes tickets to issues. The `research` rule group reads the last value of a gauge that each run sets, zero included. `tests/prometheus/test_k8s_monitoring_alerting.py` runs `promtool test rules` on each group with a fixture file.

## Existing Tool Considered
- Kubernetes CronJob (`concurrencyPolicy: Forbid`) runs the schedule, as CronJob `renovate` does. Prometheus and Alertmanager give the alerts, through the existing OTLP gauge path (`telemetry/instruments.py`, `emit`) and the existing product rule file. No new tool is needed.
- OpenTofu with the GitHub provider plans drift, but ADR 0035 moved the repository settings to the command, so a second planner would hold a second copy of the baseline.
- Build cost: about 150 lines of code, 60 lines of manifest and rules, 8 tests and the documents; about 0.4M tokens and 0.5 agent-days, as the design of #6773 estimated. The code to keep is small, because it reuses the rows, the gauge path and the rule file.
- The change deletes no internal code.
