# Proposal: #7534

## Why

In #7534, ADR 0041 gates GitHub settings applies through an environment whose required reviewer is the owner. Because agent sessions share the owner's GitHub credentials, `devops gh api` must refuse mutating review endpoints on workflow runs (`POST repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` and `POST repos/{owner}/{repo}/actions/runs/{run_id}/deployment_protection_rule`) so an agent cannot approve a deployment in place of a person.

## What Changes

- Add `POST repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` and `POST repos/{owner}/{repo}/actions/runs/{run_id}/deployment_protection_rule` to `CONST_GH_API_PROTECTED_ROUTES` (`src/devops_cli/config/constants.py`) under the route class `deployment review`.
- Update `GHCommandHelp.api` (`src/devops_cli/lang/en/help.py`) and `SECURITY.md` to name `deployment review` and its two routes, and regenerate `docs/commands/gh.md` and `docs/CLI_REFERENCE.md` with `devops docs generate`.
- Add unit tests in `tests/github/test_gh_api_agent_guard.py` and `tests/commands/test_gh_cmd.py`.
- Carries a spec delta updating `openspec/specs/gh-api-agent-guard/spec.md`.

## Capabilities

### Modified Capabilities

- `gh-api-agent-guard`: Adds the `deployment review` route class covering `pending_deployments` and `deployment_protection_rule` `POST` routes and updates documentation requirements.

## Impact

- Code & Docs: `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `SECURITY.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`.
- Tests: `tests/github/test_gh_api_agent_guard.py`, `tests/commands/test_gh_cmd.py`.
- Fits in one pull request and does not wait on ADR 0041 or `#7497`.

## Feasibility

- Inspected `src/devops_cli/github/api_guard.py:63-100` (`classify_protected_route` and `require_gh_api_access`) and `src/devops_cli/config/constants.py:3184`: `{owner}`, `{repo}`, and `{run_id}` single-segment wildcards already match path segments cleanly, and `tests/github/test_gh_api_agent_guard.py` + `tests/commands/test_gh_cmd.py` cover the guard offline.

## Existing Tool Considered

Extends the existing in-repo guard `require_gh_api_access` (`src/devops_cli/github/api_guard.py:84`) and `CONST_GH_API_PROTECTED_ROUTES` (`src/devops_cli/config/constants.py:3184`) with two table rows, help/documentation updates, and unit tests (~10 lines of data + tests, ~20k tokens and under one hour). No existing open tool covers GitHub credential policy enforcement on `devops gh api`. No internal code is deleted.
