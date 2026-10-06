# Task: Scope Roadmap Reprioritization Pull Request Queries (#1246)

**Issue**: [#1246](https://github.com/dan-petty/devops-cli/issues/1246)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p0-critical
**Scope**: scope/github, type/bug

## Description

Following the introduction of merged pull request awareness in #1244, `_OPEN_PULL_REQUESTS_QUERY` requested `pullRequests(states: [OPEN, MERGED], first: $first)`. Because this queried across all branches and the full historical life of the repository without pagination, `totalCount` (536) exceeded the single-page limit of 100. This triggered `GitHubRoadmapStore._require_whole`, throwing a `GitHubOperationError: Read 100 of 536 open pull requests, so the read is incomplete.` on every execution of `devops roadmap reprioritize`. Furthermore, GitHub GraphQL defaults to `CREATED_AT` ascending, returning only the oldest 100 pull requests in repository history and missing recent pull requests.

This fix restructures the GraphQL query and payload parser:
- **Partitioned Single-Query GraphQL Selection**:
  - `_OPEN_PULL_REQUESTS_QUERY` splits selection into `openPrs: pullRequests(states: [OPEN], first: $first)` and `recentPrs: pullRequests(states: [MERGED], orderBy: {field: CREATED_AT, direction: DESC}, first: $first)`.
  - Open pull requests remain bounded and verified via `_require_whole(len(open_prs), total_count)`.
  - Recent merged pull requests are ordered newest first, retrieving relevant merged PRs for the active release without full repository enumeration.
- **Payload & Model Compatibility**:
  - `_OpenPullRequestsPayload` validates `open_prs` with `AliasChoices` supporting both `openPrs` and legacy `pullRequests` (preserving compatibility with existing test fixtures and mocks).
  - Merged PRs are deduplicated against open PRs by number.
- **Invariants**:
  - Retains single GraphQL round-trip per `devops roadmap reprioritize` run, maintaining parity with `request_plan.py` dry-run expectations.

## Acceptance Criteria

- [x] `_OPEN_PULL_REQUESTS_QUERY` queries `openPrs` and `recentPrs` (ordered newest first) in a single request.
- [x] `GitHubRoadmapStore._require_whole` only validates completeness on `openPrs`, preventing failures against historical merged PR counts.
- [x] Recent merged PRs (such as #1243 and #1245) are successfully indexed and linked to issues.
- [x] Real `devops roadmap reprioritize --plan` runs without error on the repository.
- [x] Unit tests in `tests/test_roadmap_github_store.py` cover single connection and dual connection payload parsing.
- [x] Full test suite and quality gates (`uv run devops ci`) pass 100%.
- [x] Changelog fragment `changelog.d/1246.md` exists.
