# Onboard a repository

`devops repos onboard` onboards one GitHub repository in one command ([ADR 0035](../adr/0035-the-onboard-command-owns-the-repository-settings.md), #6773). It applies the settings baseline of the template repository, opens one pull request with the files of the template, and connects the repository to the Service. It does each step that the GitHub API allows, and it prints only the steps that GitHub allows only a person to do. The command help gives a summary. This page gives the rest.

## Onboard a new repository

1. Store the release App once (person step 2 below):

   ```sh
   devops config set github.release_app_client_id <client-id>
   devops config set github.release_app_private_key --from-file <key.pem>
   ```

2. From a clean checkout of `origin/main` of devops-cli, with your own gh login, run:

   ```sh
   devops repos onboard <owner>/<name> --confirm
   ```

   Add `--create --visibility public` for a repository that does not exist yet, and `--scope <scope>` once for each Conventional Commit scope of the repository.

3. Do the person steps that the output lists at its end.

Run the command again at any time. On an onboarded repository it sends no write and exits 0. After a failure, a new run goes on from the live state. Run `devops repos onboard <owner>/<name>` first to see the plan: it reads and writes nothing.

## Modes

- `--plan` (the default) reads only: GET requests to the API, and the clone of the template by `copier`. It exits 1 when a row has a change to make, a failure or a read that failed.
- `--dry-run` sends no request and starts no program. It lists the reads of each row and each write route with its owner.
- `--confirm` writes each difference. It exits 1 when a row has a failure or a read that failed.
- `devops repos onboard --all --plan` checks each repository of `service.repos`: the drift check that the [nightly Job](#the-nightly-job) runs. After the reports it prints one line for each repository with its state: `drift`, `not readable` or `clean`. `--all` refuses `--confirm`.
- `--only <row>,...` runs only the rows that it names, such as `--only 2,3,8`.

## The baseline

The baseline is the [Copier](https://copier.readthedocs.io/) template of `github.template_repository` (default dan-petty/infra). The command renders it at the template ref: `--template-ref`, else `_commit` of `.copier-answers.yml` of the repository, else the latest release tag of the template repository, which it reads at run time. It runs the `copier` program and does not import the Copier library, because the library needs `jinja2-ansible-filters`, which is GPL3. Install the program once with `uv tool install copier`. Without it, the rows that read the baseline are `not readable`, and a person step gives the install. The rendered `github/repository.yaml` holds the settings, and it must match `templates/github-repository.schema.json` of the template at the same ref. The rendered files and the agent files of `devops ai agents --template` are the content of the template pull request.

The flags `--scope`, `--release-flow/--no-release-flow` and `--release-type` give the answers of the render only before `.copier-answers.yml` exists. After the first render, the file holds the answers, and the command refuses a flag that gives another value, with exit status 2. Change an answer with `copier update --data <question>=<answer>`. Renovate's copier manager proposes each new tag of the template.

## Rows

Each row reads the live state with GET, compares it with the baseline, and writes only the differences. A live answer can hold more keys than the baseline. GitHub leaves a field out of its answer to a token that may not read it, so rows 2 and 10 compare only the keys that the answer holds. A key that the answer does not hold is unknown, not a difference: with no other difference the row is `not readable`, its reason names the keys, and a person step names the permission and the command that reads the row with your own login (#6875). Each write goes through one route of `src/devops_cli/github/onboard/routes.py`, which names its owner.

| Row | Name | What it does |
| --- | --- | --- |
| 0 | Preflight | The token must hold the scopes `repo` and `workflow`. A 403 of the rulesets of a private repository is the limit of the Free plan (D2). The row fails on a variable or secret `SERVICE_APP_*` (#6771). With `--confirm`, a failed row 0 stops the run before its first write. For a repository that does not exist, the row checks the scopes before row 1 creates it. |
| 1 | Create | `POST /user/repos` with `auto_init`, only with `--create` and `--visibility`, and only for a repository of your login. |
| 2 | Repository | One `PATCH /repos/<repo>` with the keys of `repository` of the baseline that differ, and `has_issues: true`. A security feature that the plan does not have is left out. A commit message goes with its title, because GitHub requires the title with the message. GitHub gives the merge settings only to a token with Contents write ([get a repository](https://docs.github.com/en/rest/repos/repos#get-a-repository)). |
| 3 | Security | The vulnerability alerts, the private vulnerability reporting, the immutable releases, the CodeQL default setup and the permissions of the job token. |
| 4 | Code Quality | `not available` when GitHub answers 404, as on a plan with no Code Quality; else `state: configured`. |
| 5 | Environment | With the release flow: the environment `release`, its branch policy `main` and the variable `RELEASE_APP_CLIENT_ID` from `github.release_app_client_id`. |
| 6 | Release secret | With the release flow: `RELEASE_APP_PRIVATE_KEY`, sealed by the code of `devops gh secret sync --env`. The value comes from `--release-key-file` or the credential `github.release_app_private_key`. The row checks the secret by name, and writes it when it is missing or with `--rotate-release-key`. No output, log, plan or error holds the value. |
| 7 | App check | `GET /repos/<repo>/installation` with the JWT of each App whose ID and key the configuration holds (`service.github_app`, `renovate`). The row sends no write: each App of the account holds all of its repositories. |
| 8 | Labels | Creates each workflow label of the package and each label of `.github/labels.yml` that GitHub lacks. A label that differs stays, and the output lists it. |
| 9 | Template pull request | Adds the template files that the repository lacks on the branch `ci/repository-template`, in one commit, and opens the draft pull request `ci: add the files of the repository template`. A file that the repository holds with other text stays, and the output lists it. The row waits for the check runs of the head, at most 15 minutes. A failed check fails the row. A wait that ends first leaves the row `waiting`, and the next run goes on. |
| 10 | Ruleset | The ruleset `main` of the baseline, with each required check of the live ruleset and each check that reported on the template pull request (D3). It waits while the checks of the template pull request have not passed. GitHub gives `bypass_actors` only to a token with write access to the ruleset ([get a repository ruleset](https://docs.github.com/en/rest/repos/rules#get-a-repository-ruleset)). |
| 11 | Ready | Marks the template pull request ready and turns on auto-merge with the squash method and the head that the checks ran on. When GitHub has nothing to wait for, it merges the pull request at once, as `gh pr merge --auto` does (D3). When a commit reached the branch after the checks, the row is `waiting` and writes nothing, and the next run checks the new head. |
| 12 | Webhook | Until #4417: the hook of `service.webhook_url`, content type `json`, active, with each event of `CONST_ROADMAP_WEBHOOK_EVENTS` or `*`. A missing hook, a wrong hook, or a hook whose secret `service.webhook_secrets` lacks gets a new secret, which goes into the keyring map and into no output. |
| 13 | Service | With `--confirm` (D4): adds the repository to `service.repos`, then runs `devops k8s push-secrets --only devops/devops-cli --rotate` and `devops k8s deploy-stack --stack devops`, unless `--no-deploy`. It does this only from a clean checkout of `origin/main` of devops-cli. Unless `--no-deploy`, it also needs the environment tree (from the project profile of the current folder, else from `infra.repos`) with its Argo CD Applications and `cluster-secrets.toml`, in a checkout that is clean at its `origin/main`, and both commands get it with `--k8s-dir`. Else the row is `refused` with the reason, and the other rows run. |
| 14 | Cluster | With `--service`: the person step of the services entry of the repository in the environment repository. |
| 15 | RAG | The `indexed`, `rag visibility` and `rag schedule` reads of the Qdrant points of the repository (#3771). With `--confirm`, an index that is not current gets the ingestion pass of the repository alone, when `service.repos` holds it. The row does not change the exit code. |

A private repository on the GitHub Free plan gets no release flow (D2), also with `--release-flow`: no release workflow, no `release` environment, no key and never a repository secret, and no ruleset, because GitHub answers 403. The rows 5, 6 and 10 are `skipped`.

Each row ends in one state: `present`, `pending` (a plan found a difference), `applied`, `waiting`, `skipped`, `not available`, `person`, `refused`, `not readable` or `failed`.

## What stays with a person

The output ends with the person steps of the repository, each with the document that makes it a person step.

1. **Each repository:** run the command with your own login. Only the authenticated user creates a personal repository ([create a repository](https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user)), and rulesets need admin access ([rulesets](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset)).
2. **Once:** store the release key and the client ID with `devops config set`. GitHub never gives a secret value back ([Actions secrets](https://docs.github.com/en/rest/actions/secrets)).
3. **A private repository on the Free plan:** make it public or move the account to a paid plan to give it a release flow. GitHub gives environments on the Free plan to public repositories only ([environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)).
4. **With `--service`:** add the services entry of the repository to the environment repository and merge its pull request. Only a person merges (AGENTS.md).
5. **Only when row 7 finds an App that does not hold the repository:** add the repository to the installation in Settings > Applications ([install a GitHub App](https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party)).
6. **Only when row 13 is refused or with `--no-deploy`:** run push-secrets and deploy-stack from a clean checkout of `origin/main` of devops-cli, with an environment tree whose checkout is clean at its `origin/main`: set `infra.repos`, or give `--k8s-dir <homelab-checkout>/k8s` ([cluster](../CLUSTER.md)).
7. **Only when row 0 names a missing scope:** run `gh auth refresh -s <scope>` ([scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)).
8. **Only when the `copier` program is not on PATH:** install it with `uv tool install copier` ([Copier installation](https://copier.readthedocs.io/en/stable/#installation)).

## The nightly Job

CronJob `repos-drift` (`k8s/devops/cronjob-repos-drift.yaml`, #6783) runs the drift check each night at 03:41 UTC in the runner image ([cluster](../CLUSTER.md#repository-drift)). It runs `devops repos onboard --all --plan --only 0,1,2,3,4,5,6,7,8,9,10,11`, the rows that its token can read:

- Row 12 stays out: it needs the keyring map of the webhook secrets, a secret value, and #4417 deletes it.
- Row 13 stays out: with `--all`, `service.repos` holds each repository, so the row reads no live state.
- Rows 14 and 15 stay out: row 14 runs only with `--service`, and row 15 informs only and needs a Qdrant key.

The pod acts as the GitHub App of the Service, and `service.github_app.drift_check` makes its installation token ask for `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS` only: read on Actions, Checks, Environments, Issues, Metadata, Pull requests and Secrets, and read and write on Administration and Contents. GitHub gives the merge settings of row 2 only with Contents write, and `bypass_actors` of row 10 and the Code Quality setup of row 4 only with Administration write (#6888). The pod holds the key of the App, which can mint a write token anyway. A plan sends GET requests only: the writer of the command sends no write without `--confirm`, and `--all` refuses `--confirm`. An installation token has no OAuth scopes, and GitHub refuses it `GET /user`, so row 0 sends no such request and notes that the token reports no OAuth scopes.

`--all --plan` sets the gauge `devops_cli_repos_drift_rows` of each repository, with the label `state`:

- `drift`: the rows that are `pending`, `failed` or `waiting`, the rows off the baseline.
- `not_readable`: the rows that are `not readable`. Such a row is its own state: it is no drift, and the repository is not clean.

Each run sets both values, zero included, and a row that informs only does not count. The alerts `RepositorySettingsDrift`, `RepositorySettingsUnreadable` and `RepositoryDriftCheckStopped` read the gauge ([alerting](../../k8s/README.md#alerting)). The command exits 1 on a drift row or a not readable row, so the Job then ends `Failed`: the gauge is the report.

The rows that read the baseline need the program `copier`. The runner image gets it from the devtools image (dan-petty/devtools pull request 43). Until then, these rows are `not readable` with the person step that installs copier, and `RepositorySettingsUnreadable` fires for each repository.

The Job leaves out row 12, so it does not check the hook of the Service. Without `github.release_app_client_id` in ConfigMap `devops-cli-config`, row 5 gives the person step of the variable and does not compare its value.

## A missing dependency that a job finds

A Service row can find a project-management dependency that the repository lacks. The stage job reads `openspec/config.yaml` at the default branch in each round (`uses_openspec`). With no file, it writes no plan for an item of the repository, and each item gets a reason that names the file. The stage row also names the file in its outcome (`JobOutcome.missing`), which the later rows of the round read. A later row can start the onboarding of the repository from this record (#4664). The template adds `openspec/config.yaml`, so the hold ends when the template pull request merges.
