# Proposal: Label Taxonomy Metrics Pagination Across All Pages Without Pull Requests

## Why

Issue #1541. `get_label_taxonomy_metrics` in `src/devops_cli/github/metrics.py` counts open issues by taxonomy label from one request: `repos/{repo}/issues?state=open&per_page=100`.
The repository contains more than 100 open issues, but the function counts only the first page.
In addition, the GitHub REST issues endpoint returns pull requests, so open pull requests with taxonomy labels are counted as issues.

## What Changes

- Extend `GhCliClient.api` in `src/devops_cli/github/client.py` to support an optional `paginate: bool = False` argument. When enabled, it appends `--paginate` and sets the timeout to `DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS`.
- Add `parse_paginated_json` in `src/devops_cli/github/client.py` to parse concatenated JSON documents or arrays from `gh api --paginate`.
- Update `get_label_taxonomy_metrics` in `src/devops_cli/github/metrics.py` to read all pages via `client.api(endpoint, paginate=True)` and parse them with `parse_paginated_json`.
- Filter out items that contain a `pull_request` key so pull requests are not counted as issues.
- Update `GitHubFake` in `tests/roadmap_board_fake.py` to support `--paginate` for issue listings and allow seeding pull requests.
- Add unit tests in `tests/test_github_metrics.py` verifying that 250 open issues across three pages are counted and pull requests are excluded.

This change fits in one pull request. It changes no consumer CLI options or specs, so it sets `skip_specs: true`.

## Feasibility

The premise was verified against the codebase and GitHub API:
- `repos/{repo}/issues` returns both issues and pull requests, and pull requests contain a `pull_request` key.
- `gh api --paginate` outputs concatenated JSON arrays for paginated endpoints.
- `DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS` is already defined in `src/devops_cli/config/defaults.py`.
- `GitHubFake` can simulate `--paginate` by collecting and emitting pages sequentially.

## Existing Tool Considered

`GhCliClient` and `run_gh` already execute rate-managed GitHub CLI commands.
`gh api --paginate` is the established tool for reading all pages through `gh`.
Using `gh api --paginate` with `parse_paginated_json` reuses existing CLI capabilities and avoids external HTTP dependencies.
