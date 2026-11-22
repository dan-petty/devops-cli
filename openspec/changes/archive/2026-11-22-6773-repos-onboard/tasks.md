# Tasks

## 1. The settings of the template and the release App, and the App installation read

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `src/devops_cli/github/app_installation.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `src/devops_cli/github/app_installation.py`, `tests/github/test_app_installation.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write the failing test that `repository_installed` sends one `GET /repos/<repo>/installation` signed with the JWT of the App, and gives true for 200 and false for 404
  - Verification: `$ uv run devops ci test tests/github/test_app_installation.py`
- [x] 1.2 Add `repository_installed`, the settings `github.template_repository` and `github.release_app_client_id`, and the credential `github.release_app_private_key`
  - Verification: `$ uv run devops ci test tests/github/test_app_installation.py tests/security/test_config_declarations.py`

## 2. The command devops repos onboard

Kind: behavior. Reads: `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/github/secrets.py`, `src/devops_cli/commands/repos.py`, `tests/roadmap/test_roadmap_onboard.py`. Changes: `src/devops_cli/github/onboard/__init__.py`, `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/routes.py`, `src/devops_cli/github/onboard/baseline.py`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/service_rows.py`, `src/devops_cli/github/onboard/run.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/repository_settings.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/github/onboard/test_onboard_routes.py`, `tests/commands/test_repos_onboard.py`.

- [x] 2.1 Write the failing tests of the requirements of `repos-onboard` against a fake GitHub that holds the state of one repository, with `process_fake` for `copier`, gh and git, `keyring_store` and `qdrant`
  - Verification: `$ uv run devops ci test tests/github/onboard tests/commands/test_repos_onboard.py`
- [x] 2.2 Build the package `src/devops_cli/github/onboard/` and the command `devops repos onboard`
  - Verification: `$ uv run devops ci test tests/github/onboard tests/commands/test_repos_onboard.py`
- [x] 2.3 Write the route-ownership test: each route of `ROUTES` is owned by the command, and each write of a confirmed run matches a route
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_routes.py`

## 3. Remove devops roadmap onboard

Kind: other. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/onboard.py` (deleted), `tests/roadmap/test_roadmap_onboard.py` (deleted), `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 3.1 Delete the command, its module, `onboard_requests`, its tests and its language entries, and change each comment that names the command
  - Verification: `$ ! git grep -n -F "roadmap onboard" -- src/ tests/`

## 4. Documents

Kind: other. Reads: `docs/roadmap/onboard.md`, `README.md`. Changes: `docs/repos/onboard.md` (new), `.nav.yml`, `.gitignore`, `docs/roadmap/onboard.md` (deleted), `README.md`, `docs/index.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/guidelines/production-readiness.md`, `docs/CLI_REFERENCE.md`, `docs/commands/repos.md`, `docs/commands/roadmap.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 4.1 Write `docs/repos/onboard.md`: the one command, the modes, the rows and the person steps, and link it from the README, the index and the roadmap workflow; change the rows of the production readiness guideline to the new command
  - Verification: `$ ! git grep -n -F "roadmap onboard" -- README.md docs/index.md docs/ROADMAP_WORKFLOW.md docs/guidelines`
  - Verification: `$ git ls-files --error-unmatch docs/repos/onboard.md && uv run --group docs devops docs site build --strict`
- [x] 4.2 Regenerate the documentation
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #6783 runs `devops repos onboard --all --plan` as a nightly Job.
- #4417 removes row 12 and its webhook secret.
- #6769 adds a release App key of its own to each repository.
- The convergence of the existing repositories is item 7 of the build plan of #6773.
- dan-petty/devtools#42 adds the `copier` program to the development tools. Until then, a person installs it with `uv tool install copier`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
