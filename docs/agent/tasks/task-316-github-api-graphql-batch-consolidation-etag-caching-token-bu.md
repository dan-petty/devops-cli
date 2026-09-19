# Task 316: GitHub API GraphQL Batch Consolidation, ETag Caching & Token-Bucket Rate Optimization Research

**Issue**: [#316](https://github.com/dan-petty/devops-cli/issues/316)
**PR**: Tracking PR targeting `release/v0.2.22`
**Status**: Completed
**Milestone**: `v0.2.22`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/github`, `priority/p0-critical`

---

## 1. Description & Objectives

GitHub management was previously split between PyGithub and CLI `gh` subprocess calls, consuming excessive REST API quota through serial round-trips for issues, milestones, and pull requests.

#### Key Deliverables:
- [x] **Context & Rationale**: Documented and resolved REST round-trip overhead and quota consumption across multiple issue, pull request, and milestone queries.
- [x] **Deep Integration & Functional Extension**:
  - Implemented `GitHubGraphQLClient` in `src/devops_cli/github/graphql.py` supporting pure GraphQL operations for repository overview, issues, pull requests, and milestones.
  - Consolidated repository overview queries (`fetch_repo_overview`) into a single GraphQL round-trip fetching repository metadata, milestones, open issues, pull requests, and rate limit telemetry simultaneously.
  - Implemented local RFC 7234 ETag caching (`RFC7234ETagCache`) supporting in-memory LRU with bounded capacity (`DEFAULT_GH_GRAPHQL_CACHE_MAX_ENTRIES`) and defensive file persistence (`gh_etag_cache.json`), returning HTTP 304 cached payloads without consuming rate limit points.
  - Implemented client-side token-bucket rate optimization (`GraphQLTokenBucket`) calculating pacing delays when remaining quota approaches the safety threshold (`DEFAULT_GH_GRAPHQL_SAFETY_THRESHOLD`).
  - Implemented native GitHub webhook HMAC-SHA256 signature verification (`verify_webhook_signature`) and decoupled observer event dispatching (`WebhookEventDispatcher`).
- [x] **Code Optimization & Performance Acceleration**: Reduced multi-item query latency from multiple serial HTTP round-trips/subshells to a single batch GraphQL call with ETag short-circuiting.
- [x] **Refactoring Potential & Legacy Elimination**:
  - Unified GraphQL client into `GitHubClient.graphql` and `GitHubClient.get_repo_overview()`.
  - Added domain exceptions `GitHubGraphQLError` and `GitHubWebhookVerificationError` inheriting from `GitHubOperationError`.
- [x] **Testing & Verification**:
  - Authored 20 unit tests with structural tuple equality assertions in `tests/test_github_graphql.py`.
  - Maintained cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ project-wide.
  - 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Summary

- **Unit Tests**: 20/20 passed in `tests/test_github_graphql.py`.
- **Architectural Invariants**: Complexity check passed ($M \le 10$, nesting depth $\le 5$).
- **Gated CI Quality Gates**: All 10 gates passed locally via `uv run devops ci`.
