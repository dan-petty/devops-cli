# repos-onboard Specification

## Purpose
How `devops repos onboard` reads, compares and writes the settings, the template files and the Service connection of one GitHub repository, from one baseline of the template repository, and which steps stay with a person (#6773, ADR 0035).

## Requirements

### Requirement: One row for each step
`devops repos onboard <owner>/<name>` SHALL print rows 0 to 16 in order: preflight, create, repository, security, Code Quality, environment, release secret, App check, labels, template pull request, ruleset, ready, webhook, Service, cluster, RAG and OpenSpec. Each row SHALL show its number, its name, its state and the changes, the reason or the person step of the state. `--only <row>,...` SHALL run only the named rows, and SHALL take each row number from 0 to the last row of the run.

#### Scenario: An onboarded repository
- **WHEN** a fake GitHub holds a repository that matches the baseline, including `openspec/config.yaml` and `openspec/specs/.gitkeep`, and `--plan` runs
- **THEN** each row from 0 to 16 is `present`, `skipped` or `not available`, and the command exits 0

#### Scenario: Only one row
- **WHEN** `--only 8` runs
- **THEN** the output holds row 8 and no other step row

#### Scenario: Only the OpenSpec row
- **WHEN** `--only 16` runs
- **THEN** the command is not refused and the output holds row 16 and no other step row

### Requirement: The modes send no more than they need
`--plan`, the default, SHALL send read requests only: GET requests to the API and the clone of the template by `copier`. `--dry-run` SHALL send no request, start no program and print the reads and writes of the route table. `--confirm` SHALL write. The command SHALL refuse two mode flags, and SHALL refuse `--all` with `--confirm`.

#### Scenario: A plan of a new repository
- **WHEN** `--plan` runs on a repository that differs from the baseline
- **THEN** each request to the fake GitHub is a GET, the rows that differ are `pending` with each change, and the command exits 1

#### Scenario: A dry run
- **WHEN** `--dry-run` runs
- **THEN** the fake GitHub gets no request, no program starts, and the output lists the write routes

#### Scenario: Two modes
- **WHEN** `--plan --confirm` runs
- **THEN** the command exits 2 with an error that names the mode flags and sends no request

### Requirement: A confirm writes only the differences
With `--confirm`, each row SHALL write only the values that differ from the baseline. A second `--confirm` on the repository that the first one onboarded SHALL send no write and SHALL exit 0. A run after a failed write SHALL go on from the live state.

#### Scenario: Two confirmed runs
- **WHEN** `--confirm` runs two times on a new repository of the fake GitHub, and its template pull request merges between the runs
- **THEN** the first run sends the writes of the routes, and the second run sends only GET requests and exits 0

### Requirement: Each write goes through the route table
Each write of the command SHALL go through one route of `ROUTES`, which names its row, method, path form and owner. No route SHALL write a setting of another owner: an organization or transfer route of OpenTofu, a status label or a comment of the Service, or a direct write of a file to the default branch. A route of `POST /graphql` SHALL name its mutations, and the writer SHALL refuse a document with another top field.

#### Scenario: The table holds no route of another owner
- **WHEN** the route-ownership test reads `ROUTES`
- **THEN** no route matches an organization, transfer, issue label, issue comment or contents route

#### Scenario: Each request of a run is a route
- **WHEN** `--confirm` runs on a new repository of the fake GitHub
- **THEN** each write request that the fake gets matches a route of `ROUTES`, and each GraphQL mutation is a mutation of a route

#### Scenario: A mutation outside its route
- **WHEN** a row sends `addComment` through the route `pull-ready`
- **THEN** the writer refuses it and sends no request

### Requirement: The baseline comes from the template at one ref
The command SHALL render the Copier template of `github.template_repository` with the `copier` program at the template ref: `--template-ref`, else `_commit` of `.copier-answers.yml` of the repository, else the latest release tag of the template repository. It SHALL validate the rendered `github/repository.yaml` with `templates/github-repository.schema.json` of the template at the same ref. A baseline that cannot be read SHALL make each row that reads it `not readable` with the reason.

#### Scenario: The latest release
- **WHEN** the repository has no `.copier-answers.yml` and no `--template-ref` is given
- **THEN** `copier copy` gets `--vcs-ref` with the `tag_name` of the latest release of the template repository

#### Scenario: A file that the schema refuses
- **WHEN** the rendered `github/repository.yaml` holds a key that the schema does not name
- **THEN** the baseline rows are `not readable`, and the reason names the schema

#### Scenario: No copier program
- **WHEN** `copier` is not on PATH
- **THEN** the baseline rows are `not readable`, the reason names the program, and a person step gives its install with the document of Copier

### Requirement: The answers file wins over the flags
When `.copier-answers.yml` is on the default branch, the command SHALL render with its answers and its `_commit`, and SHALL refuse with a usage error a flag that gives another value: `--scope`, `--release-flow`, `--release-type` or `--template-ref`.

#### Scenario: A scope that differs
- **WHEN** the answers file holds `scopes: api` and `--scope worker` is given
- **THEN** the command exits 2 with an error that names the flag and the file, and sends no write

### Requirement: The preflight stops a confirm
Row 0 SHALL read the OAuth scopes of a gh token and SHALL need `repo` and `workflow`. It SHALL probe the rulesets of the repository, and a 403 on a private repository SHALL mark the Free plan limit (D2). It SHALL fail when the baseline or a secret of the repository names `SERVICE_APP_*`. With `--confirm`, a failed row 0 SHALL stop the run before the first write. For a repository that does not exist, row 0 SHALL check the scopes before row 1 creates it.

#### Scenario: A token without workflow
- **WHEN** the token holds the scope `repo` only and `--confirm` runs
- **THEN** row 0 is `failed` and names `workflow`, and the fake GitHub gets no write

#### Scenario: A token without workflow and a create
- **WHEN** the fake GitHub has no repository, the token holds the scope `repo` only and `--create --visibility public --confirm` runs
- **THEN** row 0 is `failed`, row 1 is `skipped`, and the fake GitHub gets no write

### Requirement: The preflight of an App token reads no user
When the process acts as the GitHub App, row 0 SHALL send no `GET /user`, because GitHub refuses it to an installation token, and SHALL note that the token reports no OAuth scopes.

#### Scenario: The drift check as the App
- **WHEN** the process acts as the GitHub App, the fake GitHub refuses `GET /user` to an installation token, `service.repos` holds one onboarded repository, and `--all --plan` runs
- **THEN** the fake GitHub gets no `GET /user`, row 0 is `present` with the reason `the token reports no OAuth scopes`, and each request is a GET or the token exchange

### Requirement: The create row runs with create only
Row 1 SHALL be `present` for a repository that exists. For a missing repository, it SHALL send `POST /user/repos` with `auto_init` and the visibility of `--visibility` only with `--create` and `--confirm`. Without `--create`, the row SHALL be `failed` with the step, and the later rows SHALL be `skipped`.

#### Scenario: A missing repository without create
- **WHEN** the fake GitHub has no repository and `--plan` runs
- **THEN** row 1 is `failed` and names `--create`, and rows 2 to 15 are `skipped`

### Requirement: The settings rows follow the baseline
Row 2 SHALL compare the `repository` body of the baseline and `has_issues: true` with `GET /repos/<repo>` and SHALL send one `PATCH` with the keys that differ. Row 3 SHALL compare `vulnerability_alerts`, `private_vulnerability_reporting`, `immutable_releases`, `code_scanning_default_setup` and `actions_workflow_permissions` with their endpoints. A key of `security_and_analysis` that the live answer does not hold, and a default setup that answers 403 or 404, SHALL be `not available`.

#### Scenario: Merge commits are on
- **WHEN** the repository allows merge commits and `--confirm` runs
- **THEN** one `PATCH /repos/<repo>` holds `allow_merge_commit: false` and no key that matches

#### Scenario: A commit message that drifts
- **WHEN** only the squash commit message of the repository differs and `--confirm` runs
- **THEN** the `PATCH` holds the message and its title, because GitHub requires the title with the message

### Requirement: Code Quality that the plan does not have
Row 4 SHALL read `GET /repos/<repo>/code-quality/setup`. A 404 SHALL be `not available`, and the run SHALL go on. Another answer with a state other than `configured` SHALL get `PATCH` with `state: configured`.

#### Scenario: Not available
- **WHEN** the fake GitHub answers 404 for the Code Quality setup
- **THEN** row 4 is `not available`, and the next rows run

### Requirement: No release flow on a private Free repository
A private repository whose ruleset probe answers 403 SHALL get no release flow, also with `--release-flow`: the render SHALL answer `release_flow: false`, rows 5 and 6 SHALL be `skipped`, and no secret SHALL go to the repository. A 403 of the environments API SHALL be a person step with the document of environments.

#### Scenario: A private repository on the Free plan
- **WHEN** the repository is private, the rulesets probe answers 403 and `--confirm` runs
- **THEN** rows 5, 6 and 10 send no write, and the person steps name the plan limit

### Requirement: The release environment and its variable
Row 5 SHALL write each environment of the baseline with its deployment branch policy, each missing branch policy, and each variable from its setting: `RELEASE_APP_CLIENT_ID` from `github.release_app_client_id`. A variable with no value set SHALL be a person step that names the setting.

#### Scenario: A new environment
- **WHEN** the repository has no environment `release` and `--confirm` runs
- **THEN** the run sends `PUT` of the environment, `POST` of the policy `main` and `POST` of the variable with the configured value

### Requirement: The release key comes by reference
Row 6 SHALL check each secret of the environment by name, and SHALL seal and write a missing secret, or each secret with `--rotate-release-key`, through `sync_repository_secrets` with the environment. The value of `RELEASE_APP_PRIVATE_KEY` SHALL come from `--release-key-file` or from the credential `github.release_app_private_key`. No output, log record, plan or error text SHALL hold the value. A missing value SHALL be a person step that names the credential.

#### Scenario: A key from a file
- **WHEN** `--release-key-file` names a file that holds a known test value and `--confirm` runs
- **THEN** gh gets the sealed body on stdin, and neither the output nor the log records nor the argv of a program hold the value

### Requirement: The App check reads only
Row 7 SHALL read `GET /repos/<repo>/installation` with the JWT of each App whose ID and key the configuration holds, and SHALL send no write. A 404 SHALL be a person step that names the App. With no configured App, the row SHALL be `not readable` with the reason.

#### Scenario: An App that is not installed
- **WHEN** the fake GitHub answers 404 for the installation of the Service App
- **THEN** row 7 is `person`, the person steps name the App, and no request of the run is a PUT of an installation

### Requirement: Labels are created and never edited
Row 8 SHALL create each workflow label of the package and each label of `.github/labels.yml` that the repository lacks: the file of the default branch, else the rendered file. A label that differs SHALL be kept and listed.

#### Scenario: A differing label
- **WHEN** a label of the file has another color on GitHub and `--confirm` runs
- **THEN** the run creates the missing labels, lists the differing label as kept and sends no PATCH of a label

### Requirement: The template pull request adds the missing files
Row 9 SHALL compare each rendered file and each agent file of `devops ai agents --template` with the default branch. It SHALL add only the files that the repository lacks, on the branch `ci/repository-template`, in one commit of the Git data API, and SHALL open a draft pull request. A file that the repository holds with other text SHALL be kept. It SHALL wait for the check runs of the head: a failed check SHALL fail the row, and a wait past its limit SHALL be `waiting`.

#### Scenario: A repository with its own pre-commit file
- **WHEN** the repository holds `.pre-commit-config.yaml` with other text and `--confirm` runs
- **THEN** the tree of the commit does not hold that file, and the row lists it as kept

#### Scenario: Checks that do not end
- **WHEN** the check runs of the head stay `in_progress` past the wait
- **THEN** row 9 is `waiting`, and rows 10 and 11 send no write

### Requirement: The ruleset requires the reported and the declared checks
Row 10 SHALL write the ruleset `main` of the baseline with each required check of the live ruleset that no check run contradicts, each check run of the template pull request that ended `success` and is no matrix leg, and the required checks rule of the `github/repository.yaml` of the default branch. That file SHALL win for each parameter that it sets and each check that it names. It SHALL send `POST` when no ruleset has the name, and `PUT` only on a difference.

#### Scenario: The checks of the template pull request
- **WHEN** the check run `PR title / Semantic PR title` passed on the template pull request and `--confirm` runs
- **THEN** the ruleset requires that check and no other

#### Scenario: The checks of the repository file in a plan
- **WHEN** the `github/repository.yaml` of the default branch requires `K8s` and `Lint`, the live ruleset requires only `PR title / Semantic PR title`, and `--plan` runs
- **THEN** row 10 is `pending` with the change `ruleset main: required checks K8s, Lint, PR title / Semantic PR title`, and the run sends no write

#### Scenario: The checks of the repository file in a confirmed run
- **WHEN** that file requires `K8s` and `Lint` and sets the strict required status checks policy to true, the live ruleset requires `PR title / Semantic PR title`, and `--confirm` runs two times
- **THEN** the first run sends one `PUT` of the ruleset, which requires `K8s`, `Lint` and `PR title / Semantic PR title` with the strict policy, and the second run sends no write

### Requirement: The command starts the merge of the template pull request
After the checks of the template pull request pass, row 11 SHALL mark it ready and SHALL turn on auto-merge with the squash method and the head that the checks ran on. When GitHub reports that the pull request can merge now, the row SHALL merge it with the squash method and that head. When the head of the pull request is not the head that the checks ran on, the row SHALL be `waiting` and SHALL send no write.

#### Scenario: A pull request with nothing to wait for
- **WHEN** the merge state of the pull request is `CLEAN`
- **THEN** the row sends `markPullRequestReadyForReview` and `mergePullRequest`, and no `enablePullRequestAutoMerge`

#### Scenario: A head that moves after its checks
- **WHEN** a commit reaches the template branch after the run reads the checks of its head
- **THEN** row 11 is `waiting`, and the pull request does not merge and gets no auto-merge

### Requirement: The webhook row writes the hook and keeps its secret
Row 12 SHALL be `present` when one active hook has `service.webhook_url`, the content type `json`, each event of `CONST_ROADMAP_WEBHOOK_EVENTS` or `*`, and its secret in `service.webhook_secrets`. With `--confirm`, a missing hook SHALL get `POST` with a new secret that goes into the keyring map `service.webhook_secrets` and into no output. A wrong hook SHALL get `PATCH` with a new secret only in a run that does row 13 with its deploy.

#### Scenario: A hook that sends every event
- **WHEN** the hook sends `*` and the keyring map holds its secret
- **THEN** row 12 is `present`

#### Scenario: A new hook
- **WHEN** the repository has no hook and `--confirm` runs
- **THEN** the fake GitHub gets one `POST` of a hook, the keyring map holds the secret of the hook, and the output does not hold the secret

### Requirement: The Service row runs only from a clean main
With `--confirm`, row 13 SHALL add the repository to `service.repos` and, unless `--no-deploy`, push `devops/devops-cli` with `--rotate` and deploy stack `devops` when it changed `service.repos` or a webhook secret. It SHALL do so only from a clean checkout of `origin/main` of devops-cli and, for a deploy, with an environment tree whose checkout is clean at its `origin/main` and which holds an Application and the Secret table. Else the row SHALL be `refused`.

#### Scenario: A dirty checkout
- **WHEN** `git status --porcelain` lists a file and `--confirm` runs
- **THEN** row 13 is `refused` and names the file count, the config file keeps its repository list, and no `devops k8s` program starts

#### Scenario: A clean main
- **WHEN** the checkout and the infra checkout are clean at `origin/main` and `--confirm` runs on a repository outside `service.repos`
- **THEN** the config file lists the repository, and the run starts push-secrets and deploy-stack, each with `--k8s-dir` at the tree that the row checked

#### Scenario: A dirty or stale infra checkout
- **WHEN** the infra checkout has a changed file, is not at `origin/main`, or its fetch fails
- **THEN** row 13 is `refused`, names the environment tree and the reason, and no `devops k8s` program starts

#### Scenario: A tree that cannot deploy
- **WHEN** no source gives a tree, the tree holds no Application or no `cluster-secrets.toml`, or it is in no git checkout
- **THEN** row 13 is `refused` with the reason, and no `devops k8s` program starts

### Requirement: The cluster row is a person step
With `--service`, row 14 SHALL add the person step of the services entry in the environment repository. Without `--service`, the row SHALL be `skipped`.

#### Scenario: A service repository
- **WHEN** `--service` is given
- **THEN** row 14 is `person`, and the person steps name the services entry

### Requirement: The RAG row reports the index
Row 15 SHALL print the `indexed`, `rag visibility` and `rag schedule` reads of the Qdrant points of the repository. With `--confirm` and a repository in `service.repos`, it SHALL run the ingestion pass for that repository alone and SHALL print the point count of each collection. The row SHALL not change the exit code.

#### Scenario: An unreadable store
- **WHEN** Qdrant cannot be read and every other row is `present`
- **THEN** the RAG reads are `not readable` with the reason, and the command exits 0

### Requirement: The person steps end the output
The output SHALL end with each person step that stays for the repository, each with the GitHub document that makes it a person step. A repository with no person step SHALL print that no step stays.

#### Scenario: A missing release key
- **WHEN** no release key is set and `--plan` runs on a public repository
- **THEN** the last lines name `devops config set github.release_app_private_key` and the document of Actions secrets

### Requirement: The drift check reads every Service repository
`devops repos onboard --all --plan` SHALL run the plan of each repository of `service.repos`, SHALL print each report, and SHALL exit 1 when any of them has a `pending`, `failed` or `not readable` row.

#### Scenario: One repository drifts
- **WHEN** `service.repos` holds two repositories and one of them allows merge commits
- **THEN** both reports print, each request is a GET, and the command exits 1

### Requirement: The command is documented
`docs/repos/onboard.md` SHALL give the command, its modes, its rows and the person steps, and the README SHALL link it.

#### Scenario: The documents
- **WHEN** `uv run devops ci docs` runs
- **THEN** it passes, and `docs/CLI_REFERENCE.md` lists `devops repos onboard` and not `devops roadmap onboard`

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

### Requirement: A key that the reply does not hold is not readable
Rows 2 and 10 SHALL compare only the top-level keys of the baseline that the reply of GitHub holds, and SHALL NOT give a key that the reply does not hold as a change. A row with such a key and no other difference SHALL be `not readable`: its reason SHALL name each such key, and a person step SHALL name the permission that GitHub needs and the command `devops repos onboard <repo> --plan --only <row>`.

#### Scenario: A reply without the merge settings
- **WHEN** the reply of `GET /repos/<repo>` holds none of the 8 merge keys of the baseline, each other key matches, and `--plan` runs
- **THEN** row 2 is `not readable` with no change, the reason names each merge key, a person step names Contents write and the document "Get a repository", and the run sends no write

#### Scenario: A reply without the merge settings and with another difference
- **WHEN** the reply of `GET /repos/<repo>` holds none of the 8 merge keys of the baseline and holds `has_issues: false`, and `--plan` runs
- **THEN** row 2 is `pending` with the one change `has_issues: True`, and the reason names each merge key

#### Scenario: A reply with the merge settings of the baseline
- **WHEN** the reply of `GET /repos/<repo>` holds each key of the baseline with its value, and `--plan` runs
- **THEN** row 2 is `present`

#### Scenario: A ruleset reply without the bypass actors
- **WHEN** the reply of `GET /repos/<repo>/rulesets/<id>` holds no `bypass_actors`, each other key matches the baseline, and `--plan` runs
- **THEN** row 10 is `not readable`, the reason names `bypass_actors`, a person step names write access to the ruleset, and the run sends no write

### Requirement: Template pull request requests the repository owner as reviewer
When row 9 of `devops repos onboard` holds a template pull request whose author differs from `ctx.options.repo.owner` and whose `requested_reviewers` does not include the owner, `--confirm` SHALL request a review from `ctx.options.repo.owner` through route `template-pull-reviewers` (`POST /repos/{repo}/pulls/{pull}/requested_reviewers`, `RouteOwner.TEMPLATE_PULL`). When the pull request author equals the repository owner, no `requested_reviewers` request SHALL be sent.

#### Scenario: Bot-authored template pull request requests owner review
- **WHEN** `devops repos onboard --confirm --only 9` creates the template pull request authored by `devops-cli-service[bot]` on `example-org/app`
- **THEN** `RouteWriter` sends `POST /repos/example-org/app/pulls/1/requested_reviewers` with `{"reviewers": ["example-org"]}`

#### Scenario: Owner-authored template pull request skips self-review
- **WHEN** `devops repos onboard --confirm --only 9` creates the template pull request authored by `example-org` on `example-org/app`
- **THEN** no request is sent to `POST /repos/example-org/app/pulls/1/requested_reviewers`

### Requirement: A default webhook URL is a person step
Row 12 SHALL report the state `person` with one step that names the setting `service.webhook_url` when the setting holds its default value. It SHALL send no request to a repository hooks route and SHALL plan no hook in that case.

#### Scenario: A default webhook URL plans no hook
- **WHEN** a test in `tests/commands/test_repos_onboard.py` runs `devops repos onboard example-org/app --plan` over the fake GitHub API with `service.webhook_url` at its default value
- **THEN** row 12 holds the state `person`, its step names `service.webhook_url`, the row holds no change, and the fake records no request to a hooks route

#### Scenario: A confirm with the default webhook URL writes no hook
- **WHEN** a test in `tests/commands/test_repos_onboard.py` runs `devops repos onboard example-org/app --confirm --only 12` over the fake GitHub API with `service.webhook_url` at its default value
- **THEN** the fake records no POST and no PATCH to a hooks route, and row 12 holds the state `person`

### Requirement: The step of a withheld secret says why
The step of a withheld secret SHALL name the reason (row 13 is not in `--only`, `--no-deploy`, or the refusal reason of the clean-checkout checks) and the command `devops repos onboard <repo> --confirm --only 12,13`, and SHALL name no deploy-stack.

#### Scenario: A withheld secret with no deploy
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed row 12 with an existing hook whose secret the map lacks and `--no-deploy`
- **THEN** the step of row 12 names `--no-deploy` and `--confirm --only 12,13`, and no step of the run names deploy-stack

### Requirement: The webhook secret write needs the Service row
Row 12 SHALL write a new secret to an existing hook only in a run that does row 13 with its deploy and passes the clean-checkout checks that row 13 makes. With `--no-deploy`, with row 13 out of `--only`, or with a checkout that row 13 refuses, it SHALL report the difference, write nothing, and give one step that names `service.webhook_secrets` and the reason.

#### Scenario: An existing hook with row 13 out of the run
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed row 12 with a set `service.webhook_url`, an existing hook whose secret the map lacks, and row 13 out of `--only`
- **THEN** the fake records no PATCH to the hook, row 12 holds the state `pending`, and its step names `service.webhook_secrets`

#### Scenario: An existing hook with no deploy
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed row 12 with an existing hook whose secret the map lacks and `--no-deploy`
- **THEN** the fake records no PATCH to the hook, and row 12 holds the state `pending`

#### Scenario: An existing hook with a refused row 13
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed run with an existing hook whose secret the map lacks and a devops-cli checkout whose `git status` lists one file
- **THEN** the fake records no PATCH to the hook, row 12 holds the state `pending`, its step names the changed file count, and row 13 is `refused`

#### Scenario: An existing hook with row 13 in the run
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed run with row 13 in `--only`, a set `service.webhook_url`, clean checkouts, and an existing hook whose secret the map lacks
- **THEN** the fake records one PATCH to the hook that carries the new secret, the map `service.webhook_secrets` holds that secret, and one `push-secrets` starts

### Requirement: The OpenSpec row reads present
`devops repos onboard` SHALL print row 16 `openspec` as `present` when the default branch holds `openspec/config.yaml` with `schema: spec-driven` and the folder `openspec/specs/` exists, and the command SHALL write nothing for that row.

#### Scenario: A complete OpenSpec setup
- **WHEN** The default branch holds `openspec/config.yaml` with the schema `spec-driven` and `openspec/specs/.gitkeep`, and `--plan` runs
- **THEN** Row 16 is `present`, the row writes nothing, and the command exits 0

### Requirement: The OpenSpec row reads missing
The command SHALL print row 16 as `missing`, with `openspec/config.yaml` in its reason, when the default branch holds no `openspec/config.yaml` and the head of the open template pull request that row 9 recorded in the same run does not pass the present conditions. When that pull request is open, the reason SHALL also name the condition that its head fails.

#### Scenario: A repository with no OpenSpec
- **WHEN** The default branch holds no `openspec/config.yaml` and no template pull request is open
- **THEN** Row 16 is `missing`, its reason names `openspec/config.yaml`, and the command exits 1

#### Scenario: A template pull request with no specs folder
- **WHEN** The default branch holds no `openspec/config.yaml`, and the open template pull request holds it and no `openspec/specs/`
- **THEN** Row 16 is `missing`, and its reason names `openspec/config.yaml` and the specs folder that the pull request lacks

### Requirement: The OpenSpec row reads invalid
The command SHALL print row 16 as `invalid`, with the failed condition in its reason, when the default branch holds `openspec/config.yaml`, no open template pull request passes the present conditions, and the file does not parse as YAML, names a schema other than `spec-driven`, or the folder `openspec/specs/` does not exist. For a missing specs folder the reason SHALL name the next step: the `copier update` of the template or a commit of `openspec/specs/.gitkeep`.

#### Scenario: A config file of another schema
- **WHEN** `openspec/config.yaml` names a schema other than `spec-driven`
- **THEN** Row 16 is `invalid` and its reason names the schema that it read

#### Scenario: A config file that does not parse
- **WHEN** `openspec/config.yaml` is not valid YAML
- **THEN** Row 16 is `invalid` and its reason names the parse failure

#### Scenario: No specs folder
- **WHEN** `openspec/config.yaml` names `spec-driven` and the default branch holds no file under `openspec/specs/`
- **THEN** Row 16 is `invalid`, and its reason names `openspec/specs/` and the `copier update` step

### Requirement: The OpenSpec row reads waiting on the template pull request
The command SHALL print row 16 as `waiting`, with the number of the open template pull request in its reason, when the default branch fails the present conditions and the head of the template pull request that row 9 recorded in the same run passes them. With `--only 16`, row 9 does not run, and the row SHALL read the default branch alone.

#### Scenario: A config file only on the template branch
- **WHEN** The default branch holds no `openspec/config.yaml` and the open template pull request holds it and `openspec/specs/.gitkeep`
- **THEN** Row 16 is `waiting`, its reason names that pull request, and the row does not make the command exit 1

#### Scenario: A specs folder only on the template branch
- **WHEN** The default branch holds `openspec/config.yaml` and no `openspec/specs/`, and the open template pull request adds `openspec/specs/.gitkeep`
- **THEN** Row 16 is `waiting` and not `invalid`

### Requirement: The OpenSpec states count as drift
The drift check SHALL count `missing` and `invalid` of row 16 as drift, because both make the command exit 1.

#### Scenario: A repository with an invalid OpenSpec setup
- **WHEN** The drift check reads a repository whose row 16 is `invalid`
- **THEN** The repository is reported as drift and not as clean

### Requirement: The OpenSpec config comes from the repository template
The command SHALL write `openspec/config.yaml` and `openspec/specs/.gitkeep` only as files of the render of the repository template, and devops-cli SHALL hold no OpenSpec config template of its own.

#### Scenario: The written config file
- **WHEN** `--confirm` adds `openspec/config.yaml` to a repository
- **THEN** The file in the template pull request equals the file of the render of the template, byte for byte

### Requirement: The OpenSpec files reach the repository in one pull request
With `--confirm`, the template pull request of row 9 SHALL carry the OpenSpec files of the template with the other template files, and it SHALL NOT overwrite a file that the default branch holds. A second `--confirm` SHALL create no commit and no second pull request while that pull request is open.

#### Scenario: Both rows need files
- **WHEN** One run finds the label rule of #3742 and the `openspec` row missing
- **THEN** The command opens one pull request that holds `.github/labels.yml`, `openspec/config.yaml` and `openspec/specs/.gitkeep`

#### Scenario: A config file that already exists
- **WHEN** The default branch holds `openspec/config.yaml` with other text
- **THEN** The pull request adds no `openspec/config.yaml` and the existing file is unchanged

#### Scenario: A second confirm
- **WHEN** The user runs `--confirm` again while the template pull request is open
- **THEN** The command creates no commit and opens no second pull request

### Requirement: The merged tree passes the strict OpenSpec validation
After the template pull request merges, the pinned `openspec validate --specs --strict` SHALL exit 0 over the OpenSpec tree of the default branch, and a live test SHALL run that pinned command over the merged tree of a scratch repository that the git fake builds.

#### Scenario: A scratch repository
- **WHEN** The test merges the template pull request in a scratch repository that the git fake builds and runs the pinned `openspec validate --specs --strict` over the merged files
- **THEN** The run exits 0 and the default branch holds the OpenSpec config file and the specs placeholder

### Requirement: The onboard document describes the OpenSpec row
`docs/repos/onboard.md` SHALL describe the `openspec` row, its states and the OpenSpec files of the repository template, and `uv run devops ci docs` SHALL exit 0 on the document.

#### Scenario: The onboard document
- **WHEN** A reader opens `docs/repos/onboard.md` after the merge
- **THEN** The document names `present`, `missing`, `invalid` and `waiting`, the marked `Product:` context line and `openspec/specs/.gitkeep`, and `uv run devops ci docs` exits 0

### Requirement: Row 10 refuses a repository file that does not load
A `github/repository.yaml` of the default branch that does not load, or that the schema of the template at the ref of the baseline refuses, SHALL make row 10 `not readable` with a reason that names the file, and row 10 SHALL send no write.

#### Scenario: A repository file that is not YAML
- **WHEN** the `github/repository.yaml` of the default branch is not valid YAML and `--confirm` runs
- **THEN** row 10 is `not readable`, the reason names the file and the line, and the run sends no write

### Requirement: A skipped check run adds no required check
Row 10 SHALL add a required check only from a check run of the template pull request that ended with the conclusion `success`. A check run that ended `skipped` SHALL add no check. Row 10 SHALL leave a live required check out of the desired ruleset when each check run of its name ended `skipped`, and the change line of the row SHALL name it after `; dropped`.

#### Scenario: Skipped reusable-workflow job
- **WHEN** the template pull request reported `K8s` as `skipped` and `PR title / Semantic PR title` as `success`
- **THEN** the ruleset `main` requires `PR title / Semantic PR title` and no check named `K8s`

#### Scenario: Passing check
- **WHEN** the template pull request reported `Tests` as `success`
- **THEN** the ruleset `main` requires `Tests`

#### Scenario: A live required check that only a skipped check run gave
- **WHEN** the live ruleset requires `K8s` and `PR title / Semantic PR title`, and the open template pull request reported `K8s` as `skipped`
- **THEN** row 10 is `pending` with the change `ruleset main: required checks PR title / Semantic PR title; dropped K8s`

### Requirement: A matrix leg gives way to its job name
Row 10 SHALL NOT add the name of a matrix leg as a required check when a check run of the name of its job ended with the conclusion `success`. A matrix leg is a check name of the shape `<job> (<values>)`. Row 10 SHALL leave out a live required check of that shape when a check run of the name of its job ended `success`, and the change line of the row SHALL name it after `; dropped`.

#### Scenario: Skipped matrix legs
- **WHEN** the template pull request reported `Tests & Coverage` as `success` and `Tests & Coverage (shard 1 of 5)` as `skipped`
- **THEN** the ruleset `main` requires `Tests & Coverage` and no check named `Tests & Coverage (shard 1 of 5)`

#### Scenario: Passing matrix legs
- **WHEN** the template pull request reported `Changed-Test Independence` and `Changed-Test Independence (run 1 of 3)` both as `success`
- **THEN** the ruleset `main` requires `Changed-Test Independence` and no check named `Changed-Test Independence (run 1 of 3)`

### Requirement: Row 9 reads the checks of the open template pull request
When the repository holds each rendered file and each agent file of the template, row 9 SHALL read the check runs of the head of the open template pull request, and SHALL record the names that ended `success` and the names that ended `skipped` for row 10. A merged or closed template pull request SHALL give row 10 no check name and no check to drop: row 10 then keeps each live required check and adds the checks of the baseline and of the `github/repository.yaml` of the default branch.

#### Scenario: An open template pull request of an onboarded repository
- **WHEN** the repository holds each file of the template, the live ruleset requires `K8s`, and its open template pull request reported `K8s` as `skipped` and `PR title / Semantic PR title` as `success`
- **THEN** row 9 is `present` and the change line of row 10 names `K8s` after `; dropped`

#### Scenario: A merged template pull request with a check name that no workflow reports now
- **WHEN** the repository holds each file of the template, the live ruleset requires only `PR title / Semantic PR title`, the head of its merged template pull request reported `Semantic PR title` as `success`, and `--confirm` runs
- **THEN** rows 9 and 10 are `present`, the run sends no write, and the ruleset does not require `Semantic PR title`

#### Scenario: A merged template pull request of an onboarded repository
- **WHEN** the repository holds each file of the template, the live ruleset requires `K8s`, its newest template pull request is merged with `K8s` as `skipped` and `PR title / Semantic PR title` as `success`, and `--confirm` runs
- **THEN** rows 9 and 10 are `present`, the run sends no write, and the ruleset still requires `K8s`
