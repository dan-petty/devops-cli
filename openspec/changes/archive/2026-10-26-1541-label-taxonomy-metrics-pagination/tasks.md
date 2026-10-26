# Tasks

## 1. Failing tests

- [x] Add failing test in `tests/test_github_metrics.py` verifying that label taxonomy metrics count 250 open issues across 3 pages and exclude pull requests <!-- id: 0 -->
  - Verification: `uv run devops ci test tests/test_github_metrics.py`

## 2. Implementation

- [x] Add `paginate` option to `GhCliClient.api` and add `parse_paginated_json` in `src/devops_cli/github/client.py` <!-- id: 1 -->
  - Verification: `uv run devops ci test tests/test_github_client.py`
- [x] Update `GitHubFake` in `tests/roadmap_board_fake.py` to support `--paginate` and pull request seeding <!-- id: 2 -->
  - Verification: `uv run devops ci test tests/test_roadmap_board_read.py`
- [x] Update `get_label_taxonomy_metrics` in `src/devops_cli/github/metrics.py` to use `paginate=True`, parse with `parse_paginated_json`, and skip pull requests <!-- id: 3 -->
  - Verification: `uv run devops ci test tests/test_github_metrics.py`
- [x] Regenerate documentation <!-- id: 4 -->
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Verification and checks

- [x] Verify `fail-to-pass` check run against base <!-- id: 5 -->
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify full CI checks pass <!-- id: 6 -->
  - Verification: `uv run devops ci`
- [x] Archive OpenSpec change <!-- id: 7 -->
  - Verification: `uv run devops openspec archive 1541-label-taxonomy-metrics-pagination`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
