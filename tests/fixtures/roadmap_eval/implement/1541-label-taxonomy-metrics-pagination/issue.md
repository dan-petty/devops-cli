Found by the roadmap Service recompute audit requested by the owner on 2026-10-10 (#1539).

## Problem
Checked at release/v0.2.33.

- `get_label_taxonomy_metrics` (`src/devops_cli/github/metrics.py:363-392`) counts open issues by taxonomy label from one request: `repos/{repo}/issues?state=open&per_page=100` with no pagination (`src/devops_cli/github/metrics.py:366-368`).
- This repository has about 295 open issues, so the label gauges count only the first 100.
- The REST issues endpoint also returns pull requests, so open pull requests with `type/*` or `scope/*` labels are counted as issues.

## Proposed design
- Read every page with the client's existing pagination: `GhCliClient.api(endpoint, paginate=True)` (`src/devops_cli/github/client.py:414`) parsed by `parse_paginated_json` (`src/devops_cli/github/client.py:282`), and skip entries that have a `pull_request` key.

## Acceptance criteria
- [ ] A test with the shared GitHub fake returning 250 open issues over three pages, plus two pull requests with labels, counts 250 issues and no pull request (`tests/test_github_metrics.py`).
- [ ] The metrics job's dry run still makes zero requests.

## Feasibility
Fits one pull request: one function and its test.
