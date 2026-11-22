## Purpose

How `devops repos onboard` reads, compares and writes the settings, the template files and the Service connection of one GitHub repository, from one baseline of the template repository, and which steps stay with a person (#6773, ADR 0035).

## ADDED Requirements

### Requirement: One row for each step
`devops repos onboard <owner>/<name>` SHALL print rows 0 to 15 in order: preflight, create, repository, security, Code Quality, environment, release secret, App check, labels, template pull request, ruleset, ready, webhook, Service, cluster and RAG. Each row SHALL show its number, its name, its state and the changes, the reason or the person step of the state. `--only <row>,...` SHALL run only the named rows.

#### Scenario: An onboarded repository
- **WHEN** a fake GitHub holds a repository that matches the baseline and `--plan` runs
- **THEN** each row from 0 to 13 is `present`, `skipped` or `not available`, and the command exits 0

#### Scenario: Only one row
- **WHEN** `--only 8` runs
- **THEN** the output holds row 8 and no other step row

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
Row 0 SHALL read the scopes of the token and SHALL need `repo` and `workflow`. It SHALL probe the rulesets of the repository, and a 403 on a private repository SHALL mark the Free plan limit (D2). It SHALL fail when the baseline or a secret of the repository names `SERVICE_APP_*`. With `--confirm`, a failed row 0 SHALL stop the run before the first write. For a repository that does not exist, row 0 SHALL check the scopes before row 1 creates it.

#### Scenario: A token without workflow
- **WHEN** the token holds the scope `repo` only and `--confirm` runs
- **THEN** row 0 is `failed` and names `workflow`, and the fake GitHub gets no write

#### Scenario: A token without workflow and a create
- **WHEN** the fake GitHub has no repository, the token holds the scope `repo` only and `--create --visibility public --confirm` runs
- **THEN** row 0 is `failed`, row 1 is `skipped`, and the fake GitHub gets no write

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

### Requirement: The ruleset requires only reported checks
Row 10 SHALL write the ruleset `main` of the baseline with each required check of the live ruleset and each check that reported on the template pull request. It SHALL send `POST` when no ruleset has the name, and `PUT` only on a difference.

#### Scenario: The checks of the template pull request
- **WHEN** the check run `PR title / Semantic PR title` passed on the template pull request and `--confirm` runs
- **THEN** the ruleset requires that check and no other

### Requirement: The command starts the merge of the template pull request
After the checks of the template pull request pass, row 11 SHALL mark it ready and SHALL turn on auto-merge with the squash method and the head that the checks ran on. When GitHub reports that the pull request can merge now, the row SHALL merge it with the squash method and that head. When the head of the pull request is not the head that the checks ran on, the row SHALL be `waiting` and SHALL send no write.

#### Scenario: A pull request with nothing to wait for
- **WHEN** the merge state of the pull request is `CLEAN`
- **THEN** the row sends `markPullRequestReadyForReview` and `mergePullRequest`, and no `enablePullRequestAutoMerge`

#### Scenario: A head that moves after its checks
- **WHEN** a commit reaches the template branch after the run reads the checks of its head
- **THEN** row 11 is `waiting`, and the pull request does not merge and gets no auto-merge

### Requirement: The webhook row writes the hook and keeps its secret
Row 12 SHALL be `present` when one active hook has `service.webhook_url`, the content type `json`, each event of `CONST_ROADMAP_WEBHOOK_EVENTS` or `*`, and its secret in `service.webhook_secrets`. With `--confirm`, a missing hook SHALL get `POST` and a wrong hook SHALL get `PATCH`, each with a new secret that goes into the keyring map `service.webhook_secrets` and into no output.

#### Scenario: A hook that sends every event
- **WHEN** the hook sends `*` and the keyring map holds its secret
- **THEN** row 12 is `present`

#### Scenario: A new hook
- **WHEN** the repository has no hook and `--confirm` runs
- **THEN** the fake GitHub gets one `POST` of a hook, the keyring map holds the secret of the hook, and the output does not hold the secret

### Requirement: The Service row runs only from a clean main
With `--confirm`, row 13 SHALL add the repository to `service.repos`, and, unless `--no-deploy`, SHALL run `devops k8s push-secrets --only devops/devops-cli --rotate` and `devops k8s deploy-stack --stack devops` when the run changed `service.repos` or a webhook secret. It SHALL do so only from a clean checkout of `origin/main` of devops-cli. Otherwise the row SHALL be `refused` with the reason, and the other rows SHALL run.

#### Scenario: A dirty checkout
- **WHEN** `git status --porcelain` lists a file and `--confirm` runs
- **THEN** row 13 is `refused` and names the file count, the config file keeps its repository list, and no `devops k8s` program starts

#### Scenario: A clean main
- **WHEN** the checkout is clean at `origin/main` and `--confirm` runs on a repository outside `service.repos`
- **THEN** the config file lists the repository, and the run starts push-secrets and deploy-stack

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
