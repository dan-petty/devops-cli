# Tasks

## 1. Write failing tests first

Kind: behavior. Reads: `src/devops_cli/commands/gh.py`, `src/devops_cli/core/caller.py`, `docs/commands/gh.md`, `SECURITY.md`. Changes: `tests/github/test_gh_api_agent_guard.py`, `tests/commands/test_gh_cmd.py`.

- [x] 1.1 Write failing unit, CLI, and documentation tests in `tests/github/test_gh_api_agent_guard.py` and `tests/commands/test_gh_cmd.py` covering protected route classification across all five classes, normalization of leading slashes and query strings, open routes (`issues`, `pulls`, `labels`, `dispatches`), agent refusal vs person allowance, implicit `-f`/`--input` writes, `--dry-run` previews, and documentation coverage in `docs/commands/gh.md` and `SECURITY.md`
  - Verification: `$ uv run devops ci test tests/github/test_gh_api_agent_guard.py tests/commands/test_gh_cmd.py`

## 2. Implement protected route table, guard, and CLI enforcement

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/exceptions/git.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/github/request_classifier.py`, `src/devops_cli/commands/gh.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/exceptions/git.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/github/api_guard.py`, `src/devops_cli/commands/gh.py`.

- [x] 2.1 Add `CONST_GH_API_PROTECTED_ROUTES` to `src/devops_cli/config/constants.py`, `GitHubApiAccessRefusedError` to `src/devops_cli/exceptions/git.py` and `src/devops_cli/exceptions/__init__.py`, `gh_api_agent_refused` to `src/devops_cli/lang/en/errors.py`, implement `src/devops_cli/github/api_guard.py`, and wire `require_gh_api_argv_access` into `api_cmd` in `src/devops_cli/commands/gh.py`
  - Verification: `$ uv run devops ci test tests/github/test_gh_api_agent_guard.py tests/commands/test_gh_cmd.py`

## 3. Update security and command documentation

Kind: documentation. Reads: `src/devops_cli/lang/en/help.py`, `SECURITY.md`, `docs/commands/gh.md`. Changes: `src/devops_cli/lang/en/help.py`, `SECURITY.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`, `docs/ERRORS.md`.

- [x] 3.1 Update `HELP.gh.api` in `src/devops_cli/lang/en/help.py`, regenerate `docs/commands/gh.md` with `uv run devops docs generate`, and add a GitHub API agent write protection section in `SECURITY.md`
  - Verification: `$ uv run devops ci docs && uv run devops ci test tests/github/test_gh_api_agent_guard.py`
