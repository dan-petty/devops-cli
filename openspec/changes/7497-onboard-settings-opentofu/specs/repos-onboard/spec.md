## MODIFIED Requirements

### Requirement: One row for each step
`devops repos onboard <owner>/<name>` SHALL print rows 0, 3, 4 and 6 to 16 in order: preflight, security, Code Quality, release secret, App check, labels, template pull request, quality ruleset, ready, webhook, Service, cluster, RAG and OpenSpec. Each row SHALL show its number, its name, its state and the changes, the reason or the person step of the state. `--only <row>,...` SHALL run only the named rows of the command.

#### Scenario: An onboarded repository
- **WHEN** a fake GitHub holds a repository that matches the baseline, including `openspec/config.yaml` and `openspec/specs/.gitkeep`, and `--plan` runs
- **THEN** each row of the command is `present`, `skipped` or `not available`, the output holds no row 1, 2 or 5, and the command exits 0

#### Scenario: Only one row
- **WHEN** `--only 8` runs
- **THEN** the output holds row 8 and no other step row

#### Scenario: Only the OpenSpec row
- **WHEN** `--only 16` runs
- **THEN** the command is not refused and the output holds row 16 and no other step row

### Requirement: A confirm writes only the differences
With `--confirm`, each row SHALL write only the values that differ from the baseline. A second `--confirm` on the repository that the first one onboarded SHALL send no write and SHALL exit 0. A run after a failed write SHALL go on from the live state.

#### Scenario: Two confirmed runs
- **WHEN** `--confirm` runs two times on a repository of the fake GitHub that holds no file of the template and no setting of the rows, and its template pull request merges between the runs
- **THEN** the first run sends the writes of the routes, and the second run sends only GET requests and exits 0

### Requirement: Each write goes through the route table
Each write of the command SHALL go through one route of `ROUTES`, which names its row, method, path form and owner. No route SHALL write a setting of another owner: a setting of a root of OpenTofu, an organization or transfer route of OpenTofu, a status label or a comment of the Service, or a direct write of a file to the default branch. A route of `POST /graphql` SHALL name its mutations, and the writer SHALL refuse a document with another top field.

#### Scenario: The table holds no route of another owner
- **WHEN** the route-ownership test reads `ROUTES`
- **THEN** no route matches a route of a root of OpenTofu, or an organization, transfer, issue label, issue comment or contents route

#### Scenario: Each request of a run is a route
- **WHEN** `--confirm` runs on a repository of the fake GitHub that holds no setting of the rows
- **THEN** each write request that the fake gets matches a route of `ROUTES`, and each GraphQL mutation is a mutation of a route

#### Scenario: A mutation outside its route
- **WHEN** a row sends `addComment` through the route `pull-ready`
- **THEN** the writer refuses it and sends no request

### Requirement: No release flow on a private Free repository
A private repository whose ruleset probe answers 403 SHALL get no release flow, also with `--release-flow`: the render SHALL answer `release_flow: false`, row 6 SHALL be `skipped`, and no secret SHALL go to the repository.

#### Scenario: A private repository on the Free plan
- **WHEN** the repository is private, the rulesets probe answers 403 and `--confirm` runs
- **THEN** rows 6 and 10 send no write, and the person steps name the plan limit

### Requirement: The drift check reads every Service repository
`devops repos onboard --all --plan` SHALL run the plan of each repository of `service.repos`, SHALL print each report, and SHALL exit 1 when any of them has a `pending`, `failed` or `not readable` row.

#### Scenario: One repository drifts
- **WHEN** `service.repos` holds two repositories and one of them has immutable releases off
- **THEN** both reports print, each request is a GET, and the command exits 1

### Requirement: The drift check reports the state of each repository
`devops repos onboard --all --plan` SHALL set the gauge `devops_cli_repos_drift_rows` of each repository of `service.repos`, with the label `repo`, the key of the repository, and the label `state`. The series `drift` SHALL count the rows that are `pending`, `failed` or `waiting`, and the series `not_readable` the rows that are `not readable`. Each run SHALL set both series, zero included. A row that informs only SHALL NOT count.

#### Scenario: A pending change gives the drift report
- **WHEN** `service.repos` holds one onboarded repository that has immutable releases off, and `--all --plan` runs
- **THEN** the series `drift` of the repository is above 0, the series `not_readable` is 0, the line of the repository says `drift`, and the command exits 1

#### Scenario: No change gives no drift report
- **WHEN** `service.repos` holds one onboarded repository, and `--all --plan` runs
- **THEN** both series of the repository are 0, the line of the repository says `clean`, and the command exits 0

#### Scenario: A row that is not readable gives its own state
- **WHEN** `service.repos` holds one onboarded repository, the program `copier` is not on PATH, and `--all --plan` runs
- **THEN** the series `drift` of the repository is 0, the series `not_readable` is above 0, the line of the repository says `not readable`, and the command exits 1

## REMOVED Requirements

### Requirement: The baseline comes from the template at one ref
**Reason**: The baseline no longer holds `github/repository.yaml` or its schema, so the schema scenario has no subject.
**Migration**: The requirement "The baseline is the rendered template at one ref".

### Requirement: The preflight stops a confirm
**Reason**: The command has no create row, so the preflight no longer checks the scopes of a create.
**Migration**: The requirements "The preflight stops a confirm before the first write" and "A missing repository goes to OpenTofu".

### Requirement: The settings rows follow the baseline
**Reason**: The root of OpenTofu holds the repository, the vulnerability alerts and the workflow permissions, so rows 2 and 3 no longer compare them.
**Migration**: The requirement "The security row writes only what the provider cannot hold", and "OpenTofu holds the provider settings of each repository" of `github-settings-opentofu`.

### Requirement: The create row runs with create only
**Reason**: `github_repository` of the root `tf/github/<owner>` creates the repository when the owner applies (ADR 0041).
**Migration**: The requirement "A missing repository goes to OpenTofu" sends a missing repository to the root. The capability `github-settings-opentofu` holds the repository.

### Requirement: The release environment and its variable
**Reason**: `github_repository_environment`, `github_repository_environment_deployment_policy` and `github_actions_environment_variable` of the root hold the environment `release`, its branch policy and `RELEASE_APP_CLIENT_ID`.
**Migration**: The requirement "OpenTofu holds the provider settings of each repository" of `github-settings-opentofu`.

### Requirement: The ruleset requires the reported and the declared checks
**Reason**: `github_repository_ruleset` of the root holds the `main` ruleset, and `repositories.yaml` of the root declares each required check. No check comes from the check runs of a pull request (#7318, #7476, #7489).
**Migration**: The requirements "OpenTofu holds the provider settings of each repository" and "A plan shows the removal of a required check" of `github-settings-opentofu`.

### Requirement: A key that the reply does not hold is not readable
**Reason**: Rows 2 and 10 no longer compare the repository or the `main` ruleset. The provider reads them, and the token of a plan must read the merge settings (upstream #3382).
**Migration**: The requirement "The owner applies, and an agent plans" of `github-settings-opentofu`.

### Requirement: Row 10 refuses a repository file that does not load
**Reason**: The command reads no `github/repository.yaml`. The module types and the key check of the root check the facts of each repository.
**Migration**: The requirement "An unknown key of the facts fails the plan" of `github-settings-opentofu`.

### Requirement: A skipped check run adds no required check
**Reason**: No row derives a required check from a check run.
**Migration**: `repositories.yaml` of the root declares each required check.

### Requirement: A matrix leg gives way to its job name
**Reason**: No row derives a required check from a check run.
**Migration**: `repositories.yaml` of the root declares each required check.

### Requirement: Row 9 reads the checks of the open template pull request
**Reason**: Row 10 takes no check name from row 9. Row 9 still waits for the checks of its head, as the requirement "The template pull request adds the missing files" says.
**Migration**: `repositories.yaml` of the root declares each required check.

### Requirement: Row 10 keeps each live rule and stricter threshold
**Reason**: Row 10 writes no `main` ruleset. The first entry of each repository in `repositories.yaml` copies its live values, and a plan shows each change of a threshold before the owner applies it.
**Migration**: The requirement "The import changes nothing" of `github-settings-opentofu`.

### Requirement: Row 10 keeps each live required check
**Reason**: Row 10 writes no `main` ruleset.
**Migration**: The requirement "The import changes nothing" of `github-settings-opentofu`.

### Requirement: Row 10 ranks each live parameter of the required checks rule
**Reason**: Row 10 writes no `main` ruleset.
**Migration**: The requirement "The import changes nothing" of `github-settings-opentofu`.

### Requirement: Row 10 names each live setting that it keeps
**Reason**: Row 10 writes no `main` ruleset. The plan names each attribute that changes.
**Migration**: The requirement "A plan shows the removal of a required check" of `github-settings-opentofu`.

### Requirement: Row 10 adds each baseline rule and check that the live ruleset lacks
**Reason**: Row 10 writes no `main` ruleset.
**Migration**: The requirement "OpenTofu holds the provider settings of each repository" of `github-settings-opentofu`.

## ADDED Requirements

### Requirement: Row 10 creates the quality ruleset only
Row 10 SHALL send `POST /repos/<repo>/rulesets` with the ruleset `quality` on the default branch and the one rule `code_quality` with the severity `errors` when the repository has no ruleset of that name. It SHALL keep a ruleset `quality` that exists, with each of its rules and thresholds. It SHALL send no write to a ruleset named `main`. Its code SHALL name `integrations/terraform-provider-github#3664`.

#### Scenario: A repository with no quality ruleset
- **WHEN** the repository has no ruleset `quality` and `--confirm` runs
- **THEN** the run sends one `POST /repos/<repo>/rulesets` with the name `quality` and the one rule `code_quality`, and row 10 lists the change

#### Scenario: A quality ruleset with other thresholds
- **WHEN** the repository has a ruleset `quality` with `code_quality` of severity `warnings` and a rule `code_coverage`, and `--confirm` runs
- **THEN** row 10 is `present`, and the run sends no write to a ruleset

#### Scenario: The main ruleset stays with OpenTofu
- **WHEN** the live ruleset `main` differs from each value of the template, and `--confirm` runs
- **THEN** the run sends no `PUT` and no `DELETE` of a ruleset

### Requirement: A row number of OpenTofu is refused
`--only` SHALL refuse the numbers 1, 2 and 5 with a usage error that names the root `tf/github/<owner>` of dan-petty/homelab, because that root holds their settings (ADR 0041). The options `--create` and `--visibility` SHALL NOT exist.

#### Scenario: A row that OpenTofu holds
- **WHEN** `--only 2` runs
- **THEN** the command exits 2 with an error that names `tf/github/<owner>`, and the fake GitHub gets no request

#### Scenario: The create option
- **WHEN** `--create --visibility public` is given
- **THEN** the command exits 2 with the error of an unknown option, and the fake GitHub gets no request

### Requirement: The routes of OpenTofu are not routes of the command
`ROUTES` SHALL hold no route of a setting that a root of OpenTofu holds: `POST /user/repos`, `PATCH /repos/<owner>/<repo>`, a route under `/environments/`, `vulnerability-alerts`, `actions/permissions/workflow`, and `PUT` or `DELETE` of a ruleset by its ID.

#### Scenario: The route-ownership test
- **WHEN** the route-ownership test reads `ROUTES`
- **THEN** no route matches one of these routes

### Requirement: The baseline is the rendered template at one ref
The command SHALL render the Copier template of `github.template_repository` with the `copier` program at the template ref: `--template-ref`, else `_commit` of `.copier-answers.yml` of the repository, else the latest release tag of the template repository. The baseline SHALL be the rendered files, and the command SHALL read no `github/repository.yaml` and no schema of the template. A baseline that cannot be read SHALL make each row that reads it `not readable` with the reason.

#### Scenario: The latest release
- **WHEN** the repository has no `.copier-answers.yml` and no `--template-ref` is given
- **THEN** `copier copy` gets `--vcs-ref` with the `tag_name` of the latest release of the template repository

#### Scenario: No copier program
- **WHEN** `copier` is not on PATH
- **THEN** the baseline rows are `not readable`, the reason names the program, and a person step gives its install with the document of Copier

#### Scenario: No settings file
- **WHEN** the rendered template holds no `github/repository.yaml`, and `--plan` runs
- **THEN** no row is `not readable` for that file, and the run reads no schema of the template

### Requirement: The preflight stops a confirm before the first write
Row 0 SHALL read the OAuth scopes of a gh token and SHALL need `repo` and `workflow`. It SHALL probe the rulesets of the repository, and a 403 on a private repository SHALL mark the Free plan limit. It SHALL fail when the baseline or a secret of the repository names `SERVICE_APP_*`. With `--confirm`, a failed row 0 SHALL stop the run before the first write.

#### Scenario: A token without workflow
- **WHEN** the token holds the scope `repo` only and `--confirm` runs
- **THEN** row 0 is `failed` and names `workflow`, and the fake GitHub gets no write

### Requirement: A missing repository goes to OpenTofu
For a repository that does not exist, row 0 SHALL fail with a person step that names the root `tf/github/<owner>` of dan-petty/homelab and the apply of the owner, and each later row SHALL be `skipped`.

#### Scenario: A missing repository
- **WHEN** the fake GitHub has no repository of the name and `--confirm` runs
- **THEN** row 0 is `failed`, its person step names `tf/github/<owner>`, each later row is `skipped`, and the fake GitHub gets no write

### Requirement: The security row writes only what the provider cannot hold
Row 3 SHALL turn on private vulnerability reporting and immutable releases, and SHALL configure the code scanning default setup with the query suite `default`. It SHALL write only a value that differs from its live value, and SHALL send no request to `vulnerability-alerts` or `actions/permissions/workflow`. A default setup that answers 403 or 404 SHALL be `not available`. The code of each call SHALL name its upstream item.

#### Scenario: Immutable releases are off
- **WHEN** the repository has immutable releases off and `--confirm` runs
- **THEN** the run sends one `PUT /repos/<repo>/immutable-releases`, and no request to `vulnerability-alerts` or `actions/permissions/workflow`

#### Scenario: A default setup that GitHub refuses
- **WHEN** the fake GitHub answers 403 for the code scanning default setup and `--plan` runs
- **THEN** row 3 is `not available` for the default setup, and the next rows run
