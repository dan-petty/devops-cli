# Proposal: #5316

## Why

Agents share the owner's GitHub token and can send mutating requests (`POST`, `PATCH`, `PUT`, `DELETE`) through `devops gh api` to repository settings, rulesets, secrets, organization settings, and repository transfer endpoints (`POST repos/{o}/{r}/transfer`). Closes #5316.

## What Changes

- Add a protected route table (`CONST_GH_API_PROTECTED_ROUTES`) in `src/devops_cli/config/constants.py` covering `POST`, `PATCH`, `PUT`, and `DELETE` across repository settings, rulesets, secrets, organization settings, and repository transfer.
- Add `GitHubApiAccessRefusedError` in `src/devops_cli/exceptions/git.py` (re-exported in `src/devops_cli/exceptions/__init__.py`) and error template `gh_api_agent_refused` in `src/devops_cli/lang/en/errors.py`.
- Add `src/devops_cli/github/api_guard.py` to normalize endpoints (stripping scheme/host, leading slash, query string, and fragment), classify routes against the protected table, and refuse protected writes when `core.caller.is_agent_caller()` is true with a message naming the matched route and the owner step.
- Wire `require_gh_api_argv_access` in `src/devops_cli/commands/gh.py` (`api_cmd`) for live writes while allowing `--dry-run` to preview the planned request and keeping read-only requests and open write routes (`issues`, `pulls`, `labels`, workflow `dispatches`) unblocked.
- Update `HELP.gh.api`, regenerate `docs/commands/gh.md`, and document the protected route classes and agent write refusal in `SECURITY.md`.

## Capabilities

### New Capabilities
- `gh-api-agent-guard`: Protect repository settings, rulesets, secrets, organization settings, and repository transfer routes against agent writes via `devops gh api`.

## Impact

- `src/devops_cli/config/constants.py`
- `src/devops_cli/exceptions/git.py`, `src/devops_cli/exceptions/__init__.py`
- `src/devops_cli/lang/en/errors.py`, `src/devops_cli/lang/en/help.py`
- `src/devops_cli/github/api_guard.py`, `src/devops_cli/commands/gh.py`
- `SECURITY.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`, `docs/ERRORS.md`
- `tests/github/test_gh_api_agent_guard.py`, `tests/commands/test_gh_cmd.py`

## Feasibility

Confirmed on `origin/main` against source:
- `src/devops_cli/core/caller.py:79` provides `is_agent_caller()`.
- `src/devops_cli/github/request_classifier.py:121` provides `parse_gh_api_args()`, which resolves HTTP method including implicit `POST` from `-f`/`-F`/`--input`.
- `src/devops_cli/commands/gh.py:1445-1537` (`api_cmd`) already builds `args = ["api", endpoint, ...]` and handles `--dry-run` before invoking `run_gh`.
- `src/devops_cli/commands/gh.py` mounts `app = new_typer(...)`, whose exit seam reports `DevOpsCLIError` cleanly without tracebacks.

## Existing Tool Considered

No open tool classifies these GitHub REST API routes or refuses agent callers inside the `devops gh api` CLI wrapper; the alternatives check on #5316 recorded `none`. This change adds a declarative route table in constants and a small guard helper reusing `parse_gh_api_args` and `is_agent_caller` (~200k tokens, <1 day to build; ~15k tokens/month to maintain).
