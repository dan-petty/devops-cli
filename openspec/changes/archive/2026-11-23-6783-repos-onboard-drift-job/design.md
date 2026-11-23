# Design

## Decisions

### 1. A gauge and warning alerts report the drift
The SRE guideline makes a cause a ticket: a warning alert whose runbook row tells what to do, and Alertmanager sends the tickets to issues (`docs/guidelines/sre.md`, Alerts and routing). Rule TM5 of `docs/SERVICE_PATTERNS.md` asks a runbook row for each cause alert. The `research` group is the closest pattern: a command sets a gauge at each run, zero included, and the rule reads its last value. So the Job reports through a gauge and the product rule file, and it files no issue.

### 2. One gauge, two counts for each repository
`devops_cli_repos_drift_rows{repo, state}` holds two series for each repository:
- `state="drift"`: the rows that are `pending`, `failed` or `waiting`. These rows make the command exit 1 and are not a failed read.
- `state="not_readable"`: the rows that are `not readable`.

A row that informs only, such as the RAG row, does not count. Each run sets both series of each repository, zero included, so a clean run ends both alerts. The label `repo` holds the key of a repository of `service.repos` (rule TM3), because only `--all` sets the gauge. One repository can have both a drift row and a not readable row, and then both alerts fire. The printed line gives one state: `drift` when a drift row exists, else `not readable` when a not readable row exists, else `clean`.

### 3. The pod acts as the App with a read-only token
The pod holds one key of Secret `devops-cli`: `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, through `secretKeyRef`, as the stage Job does. `DEVOPS_CLI_SERVICE_GITHUB_APP_READ_ONLY=true` makes `configured_app` give the App the permissions `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS`: `actions`, `administration`, `checks`, `contents`, `environments`, `issues`, `metadata`, `pull_requests` and `secrets`, each `read`. These are the permissions of the GETs of rows 0 to 3 and 5 to 11. The ConfigMap leaves the setting out, as it leaves out `token_repository`, so the Service keeps its own set. The pod mounts no ServiceAccount token, and ServiceAccount `devops-cli` has no Role.

### 4. Row 0 sends no GET /user for the App
An installation token reports no OAuth scopes, and GitHub refuses it `GET /user`. `token_scopes` gives None for an App identity with no request, so row 0 notes "the token reports no OAuth scopes", as it already does for a token with no scopes header.

### 5. The Job runs the rows that a read token can read
The Job runs `devops repos onboard --all --plan --only 0,1,2,3,5,6,7,8,9,10,11`. It leaves out:
- Row 4: GitHub needs Administration write for `GET .../code-quality/setup`.
- Row 12: it needs the keyring map of the webhook secrets, a secret value, and #4417 deletes the row.
- Row 13: with `--all`, `service.repos` holds each target, so the row reads no live state.
- Row 14: it runs only with `--service`.
- Row 15: it informs only, and it needs a Qdrant key.

### 6. The schedule, the image and the limits
- Schedule `41 3 * * *` (UTC), `concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 3600`, no retry. A plan writes nothing, and the next night runs it again.
- The runner image, which is `FROM` the devtools image: the devtools image gives `copier` to the runner image when dan-petty/devtools pull request 43 merges and Renovate updates the base. Until then, the rows that read the baseline are `not readable`.
- `activeDeadlineSeconds: 1800`. The token lives 3600 s, so the deadline ends the pod first.
- The pod label `app.kubernetes.io/name: repos-drift`. The default perimeter of the namespace selects it: DNS, the gateway, the cache Valkey and Qdrant ports in namespace llm, the OTel collector and public HTTPS. It gets no key of the gateway, the cache Valkey or Qdrant.

### 7. The alerts
- `RepositorySettingsDrift`: the last value of the last 2 days of a `drift` series is above 0.
- `RepositorySettingsUnreadable`: the same for a `not_readable` series.
- `RepositoryDriftCheckStopped`: the Job sent a value in the last 7 days but none in the last 2 days. It stays quiet before the first run.

Each selector names `job="repos-drift"`, the `OTEL_SERVICE_NAME` of the pod, so a run on a workstation never counts. The window of 2 days holds the last nightly run with one day of margin.

### 8. The exit code stays
The drift check exits 1 on a drift row or a not readable row (ADR 0035). So the Job ends `Failed` on drift. No alert reads the status of the Job: the gauge is the report, and the stopped alert finds a Job that sends no report.

## Rejected alternatives
- **An issue through `devops roadmap intake`**: rejected. A write to issues needs the permission `issues: write`, and the Job holds read permissions only. A nightly issue also repeats the same drift each night. Alertmanager routes the tickets to issues (`docs/guidelines/sre.md`).
- **An init container that writes a token file, as CronJob `renovate` does**: rejected for now. The devops process gets its token from `gh auth token` or mints it from the key (`src/devops_cli/core/process.py`, `github_identity`), and it has no token-file input, so the split needs new code. The pod runs no program of a repository: `copier` renders the template of `github.template_repository` at a release tag, and the template has no tasks (#6773 design).
- **The service image**: rejected. It holds no `copier`, and the devtools image gives the tools of the runner image only (`Dockerfile`).
- **A CronWorkflow**: rejected. Rule WK2 of `docs/SERVICE_PATTERNS.md` allows a CronJob with `concurrencyPolicy: Forbid`, and the check is one step.
- **A new command `devops repos drift`**: rejected. ADR 0035 names `devops repos onboard --all --plan` as the drift check, so the apply and the check keep one code path.
- **One series whose value is a state code**: rejected. A label for each state is the Prometheus form (`kube_pod_status_phase`), and a sum or a threshold reads it directly.
- **A Job that exits 0 on drift**: rejected. ADR 0035 says that the drift check exits 1 on a pending change, and a person who runs it reads the same exit code.
