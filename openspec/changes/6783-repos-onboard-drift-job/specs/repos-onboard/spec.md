## ADDED Requirements

### Requirement: The drift check reports the state of each repository
`devops repos onboard --all --plan` SHALL set the gauge `devops_cli_repos_drift_rows` of each repository of `service.repos`, with the label `repo`, the key of the repository, and the label `state`. The series `drift` SHALL count the rows that are `pending`, `failed` or `waiting`, and the series `not_readable` the rows that are `not readable`. Each run SHALL set both series, zero included. A row that informs only SHALL NOT count.

#### Scenario: A pending change gives the drift report
- **WHEN** `service.repos` holds one onboarded repository that allows merge commits, and `--all --plan` runs
- **THEN** the series `drift` of the repository is above 0, the series `not_readable` is 0, the line of the repository says `drift`, and the command exits 1

#### Scenario: No change gives no drift report
- **WHEN** `service.repos` holds one onboarded repository, and `--all --plan` runs
- **THEN** both series of the repository are 0, the line of the repository says `clean`, and the command exits 0

#### Scenario: A row that is not readable gives its own state
- **WHEN** `service.repos` holds one onboarded repository, the program `copier` is not on PATH, and `--all --plan` runs
- **THEN** the series `drift` of the repository is 0, the series `not_readable` is above 0, the line of the repository says `not readable`, and the command exits 1

### Requirement: The drift check prints the state of each repository
After the reports, `devops repos onboard --all --plan` SHALL print one line for each repository with its state: `drift` when a row counts as drift, else `not readable` when a row counts as not readable, else `clean`. A run of one repository SHALL print no state line and SHALL set no gauge.

#### Scenario: One repository sets no gauge
- **WHEN** `devops repos onboard <owner>/<name> --plan` runs over an onboarded repository
- **THEN** the collector gets no point of `devops_cli_repos_drift_rows`

## MODIFIED Requirements

### Requirement: The preflight stops a confirm
Row 0 SHALL read the OAuth scopes of a gh token and SHALL need `repo` and `workflow`. When the process acts as the GitHub App, row 0 SHALL send no `GET /user`, because GitHub refuses it to an installation token, and SHALL note that the token reports no OAuth scopes. Row 0 SHALL probe the rulesets of the repository, and a 403 on a private repository SHALL mark the Free plan limit (D2). It SHALL fail when the baseline or a secret of the repository names `SERVICE_APP_*`. With `--confirm`, a failed row 0 SHALL stop the run before the first write. For a repository that does not exist, row 0 SHALL check the scopes before row 1 creates it.

#### Scenario: A token without workflow
- **WHEN** the token holds the scope `repo` only and `--confirm` runs
- **THEN** row 0 is `failed` and names `workflow`, and the fake GitHub gets no write

#### Scenario: A token without workflow and a create
- **WHEN** the fake GitHub has no repository, the token holds the scope `repo` only and `--create --visibility public --confirm` runs
- **THEN** row 0 is `failed`, row 1 is `skipped`, and the fake GitHub gets no write

#### Scenario: The drift check as the App
- **WHEN** the process acts as the GitHub App, the fake GitHub refuses `GET /user` to an installation token, `service.repos` holds one onboarded repository, and `--all --plan` runs
- **THEN** the fake GitHub gets no `GET /user`, row 0 is `present` with the reason `the token reports no OAuth scopes`, and each request is a GET or the token exchange
