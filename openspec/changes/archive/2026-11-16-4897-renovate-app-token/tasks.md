# Tasks

## 1. The token command (behavior)

- [x] 1.1 Write the failing tests of `devops gh app-token --app renovate` in `tests/commands/test_gh_app_token.py`: the 9 permissions and the JWT issuer for an App ID and a Client ID, mode 0600, no token in the output or the log, the dry run, a setting that is not set, and a refused permission
  - Verification: `$ uv run devops ci test tests/commands/test_gh_app_token.py`
- [x] 1.2 Add the `renovate` settings and the credential `renovate.github_app_private_key`, `GitHubApp.permissions` and `GitHubApp.key_source`, `src/devops_cli/github/app_token.py` and the command in `src/devops_cli/commands/gh.py`, with its texts in `src/devops_cli/lang/en/`
  - Verification: `$ uv run devops ci test tests/commands/test_gh_app_token.py tests/github/test_github_app_identity.py tests/commands/test_config_cmd.py tests/commands/test_config_audit_keys.py`

## 2. The name of the Renovate App (behavior)

- [x] 2.1 Change `_NOT_RENOVATE` in `tests/invariants/test_workflow_contracts.py` to `dan-petty-renovate[bot]`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 2.2 Change the job condition of `.github/workflows/fail-to-pass.yml` to skip `dan-petty-renovate[bot]`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 3. Documents

- [x] 3.1 Regenerate the documentation with `devops docs generate`, and name `dan-petty-renovate[bot]` in `docs/SDLC.md`
  - Verification: `$ uv run devops docs check`

## Workflow follow-up

- #4905 runs `devops gh app-token --app renovate --write <path>` in the init container of the Renovate CronJob, adds Secret `devops/renovate` to the Secret table, and gives the token file to the Renovate container.
- Pending a person: create the App `dan-petty-renovate`, install it, and store the 3 settings (#4893 owner steps 1 to 3).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
