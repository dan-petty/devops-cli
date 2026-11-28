# Tasks

## 1. Behavior

- [x] 1.1 Write failing unit and command tests for `deployment review` routes (`pending_deployments`, `deployment_protection_rule`)
  - Verification: `$ uv run devops ci test tests/github/test_gh_api_agent_guard.py tests/commands/test_gh_cmd.py`
- [x] 1.2 Add `deployment review` entries to `CONST_GH_API_PROTECTED_ROUTES` in `src/devops_cli/config/constants.py`
  - Verification: `$ uv run devops ci test tests/github/test_gh_api_agent_guard.py tests/commands/test_gh_cmd.py`

## 2. Documents

- [x] 2.1 Update `GHCommandHelp.api` in `src/devops_cli/lang/en/help.py`, `SECURITY.md`, and regenerate CLI documentation with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## 3. Quality Gate

- [x] 3.1 Run OpenSpec and static CI quality gates
  - Verification: `$ uv run devops openspec check`

Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
