# Proposal

## Why

In #1415, `_detect_resource` in `src/devops_cli/github/rate_limiter.py` misclassifies GitHub CLI commands.
It classifies porcelain commands such as `pr checks`, `pr list`, and `issue list` as `core` REST requests.
GitHub runs these porcelain commands through GraphQL queries and mutations.
`run_gh` paces and plans them against the core REST rate-limit quota instead of the GraphQL quota.
Also, `_detect_resource` uses substring checks on arguments.
Arguments that contain substrings like `graphql` or `search/` cause false classifications.

This change fits one pull request.

## What Changes

- Classify GraphQL-backed GitHub CLI porcelain commands with a table of command words in `src/devops_cli/config/constants.py`.
- Classify `gh api` requests using the parsed endpoint path rather than argument substrings.
- Return `core` for REST endpoints whose path segments contain substrings like `graphql` or `search`.
- Update `_detect_resource` and `gh_request_resource` to use these structured classifiers.
- Update tests to assert that `pr checks`, `pr list`, `issue list`, and related porcelain commands map to `graphql`.
- Add test coverage for false-positive substring paths.

This change alters internal request pacing and dry-run display labels.
It does not change command lines, options, or external configurations.
The change sets `skip_specs: true` in `.openspec.yaml`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/config/constants.py`: defines `CONST_GH_GRAPHQL_PORCELAIN_COMMANDS`, `CONST_GH_GRAPHQL_GROUPS`, and REST endpoint prefix constants.
- `src/devops_cli/github/rate_limiter.py`: refactors `_detect_resource` to use structured endpoint and porcelain command classification.
- `tests/test_github_rate_limiter.py`: tests porcelain and REST endpoint rate-limit resource classification.
- `src/devops_cli/roadmap/request_plan.py`: reads `gh_request_resource` for accurate dry-run labels.

## Feasibility

- Confirmed with GitHub CLI version 2.103.2 that `pr checks`, `pr list`, `pr view`, `pr edit`, `pr ready`, `pr close`, `issue list`, `issue create`, and `release list` send GraphQL operations.
- Confirmed that `label list` sends a REST `GET /repos/{owner}/{repo}/labels` request.
- Confirmed that `_detect_resource` previously returned `core` for `["pr", "checks", "1"]` and `["pr", "list"]`.
- Confirmed that `_detect_resource` previously returned `graphql` for `["api", "repos/graphql/graphql-js/issues"]` due to substring matching.
- Confirmed that `_detect_resource` previously returned `search` for `["api", "repos/octo/research/issues"]`.

## Existing Tool Considered

GitHub CLI (`gh`) and GitHub's REST and GraphQL APIs execute repository requests.
The rate limiter in DevOps CLI paces requests to prevent API rate-limit exhaustion.
No open Python library maps GitHub CLI porcelain subcommands to GitHub API quota resources.
This change replaces internal substring checks in `src/devops_cli/github/rate_limiter.py` with structured table lookups.
