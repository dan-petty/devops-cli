# Proposal: one command onboards a repository

## Why

#6773: on 2026-11-22 the onboarding of dan-petty/infra and dan-petty/devtools took more than 10 steps by hand, found one at a time: the `release` environment, its branch rule, variable and secret, the Renovate preset, the release-please files, the scope labels, the merge settings, the webhook of the Service, `service.repos`, and the checks of `devops roadmap onboard`. The settings of the repositories now differ. [ADR 0035](../../../docs/adr/0035-the-onboard-command-owns-the-repository-settings.md) records the owner decisions D1 to D4: `devops repos onboard` owns the repository settings, applies one baseline from dan-petty/infra, opens one template pull request and connects the Service. This change builds the command.

## What Changes

- Add `devops repos onboard <owner>/<name>` with `--plan` (the default: read requests only), `--dry-run` (no request) and `--confirm` (writes), and `devops repos onboard --all --plan`, the drift check of each repository of `service.repos`. The command observes a new CLI surface, so the change has a spec delta.
- The command runs rows 0 to 15 of the design of #6773 in one code path: each row reads the live state, compares it with the baseline and writes only the differences. A row writes through one route table, so a route that is not in the table cannot run. On an onboarded repository, `--confirm` sends no write and exits 0.
- The baseline comes from the Copier template of the template repository (`github.template_repository`, default dan-petty/infra) at the template ref: `--template-ref`, else `_commit` of `.copier-answers.yml` of the repository, else the latest release tag of the template repository, read at run time. The command runs the `copier` program, validates the rendered `github/repository.yaml` with the schema of the template at the same ref, and refuses an answer flag that differs from `.copier-answers.yml`.
- Rows: 0 preflight (token scopes, ruleset probe, no `SERVICE_APP_*` name), 1 create (`--create` only), 2 repository settings, 3 security features, 4 Code Quality (`not available` on 404), 5 release environment and variable, 6 release secret (by reference, through the code of `devops gh secret sync --env`), 7 App check (GET only), 8 labels, 9 template pull request, 10 ruleset `main`, 11 ready and auto-merge (D3), 12 webhook (until #4417), 13 Service (D4), 14 cluster (`--service` only, a person step), 15 RAG.
- D2: a private repository on the Free plan gets no release flow: no environment, no key and never a repository secret. A 403 of the rulesets or environments API becomes a person step.
- The output ends with the person steps that stay for the repository, each with the GitHub document that makes it a person step.
- Add the settings `github.template_repository` and `github.release_app_client_id`, and the credential `github.release_app_private_key`.
- Add `repository_installed` to `src/devops_cli/github/app_installation.py`: one GET of `/repos/<repo>/installation` signed with the JWT of an App.
- Remove `devops roadmap onboard`, `src/devops_cli/roadmap/onboard.py`, `onboard_requests` of `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_onboard.py` and `docs/roadmap/onboard.md`. Their rows move to the new command, except the row of `.github/workflows/clear-status.yml`, which #4660 removes.

## Capabilities

### New Capabilities

- `repos-onboard`: How `devops repos onboard` reads, compares and writes the settings, files and connections of a repository, and the person steps that stay.

### Modified Capabilities

- `roadmap-onboard`: All requirements are removed. The rows move to `repos-onboard`.

## Impact

- Code: `src/devops_cli/github/onboard/` (new package), `src/devops_cli/commands/repos.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/github/app_installation.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `src/devops_cli/lang/en/`.
- Removed: `src/devops_cli/roadmap/onboard.py`, `onboard_requests`, `tests/roadmap/test_roadmap_onboard.py`.
- Documents: `docs/repos/onboard.md` (new, the how-to), `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/repos.md`, `docs/commands/roadmap.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/index.md`, `docs/guidelines/production-readiness.md`.
- Tool: the command runs the `copier` program, which a person installs with the development tools. No Python dependency is added.
- The change fits one pull request. The nightly drift Job is #6783, the convergence of the existing repositories is a later item, and #4417 removes row 12.

## Feasibility

- The template: `copier.yml`, `templates/repository/**` and `templates/github-repository.schema.json` of dan-petty/infra pull request #40 (`git show HEAD:copier.yml` of branch `feat/37-repository-template`). `copier.yml` has `_subdirectory: templates/repository` and no `_tasks`, so Copier runs it without `--trust`. The latest release tag v0.2.0 of infra (`devops gh api repos/dan-petty/infra/releases/latest --jq .tag_name`) does not hold the template yet, so until #40 releases, a run names the missing `copier.yml` in the baseline rows and `--template-ref` selects a ref that holds it.
- The token of gh holds the scopes `gist, read:org, repo, workflow` (`devops gh api -i /user`, header `X-OAuth-Scopes`).
- `GET /user/installations` with the token of gh answers HTTP 403 "You must authenticate with an access token authorized to a GitHub App" (run of 2026-11-22). So row 7 reads `GET /repos/<repo>/installation` with the JWT of each App whose ID and key the configuration holds. gidgethub 6.0.1 signs the JWT (`GitHubAPI(..., app_id=, private_key=)`).
- `GET /repos/dan-petty/devops-cli/actions/secrets` lists no repository secret, and `GET .../environments` lists `release` (run of 2026-11-22).
- `src/devops_cli/github/secrets.py` seals a secret into an environment (`sync_repository_secrets(..., environment=, value=)`, #6781) and sends the PUT body on stdin.

## Existing Tool Considered

- **Copier** (copier-org/copier, MIT, 9.19.1 on PyPI, maintained): it renders the template. The command runs the `copier` program through `run_subprocess`. The library is not a dependency: copier 9.19.1 requires `jinja2-ansible-filters`, whose license is GPL3 (PyPI metadata of 1.3.2), and CONTRIBUTING.md refuses a strong-copyleft component. The template uses the filter `regex_search` of that package, so a render without it fails.
- **integrations/terraform-provider-github** (MIT, maintained): ADR 0035 rejected it for the repository settings, because its stacks and state do not exist and it cannot hold the `code_quality` rule of the ruleset.
- **gh** (`gh pr merge --auto`): row 11 does what gh does through the GraphQL API of the session: it turns on auto-merge, or merges at once when GitHub has nothing to wait for.
- Cost to build the rows: about 2.4M tokens and 2.75 agent-days (the build plan of #6773). No open tool reads each setting, writes only the differences and prints the web-UI-only steps.
- Deleted code: `src/devops_cli/roadmap/onboard.py`, the command `devops roadmap onboard` and `onboard_requests` of `src/devops_cli/roadmap/request_plan.py`.
