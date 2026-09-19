# Task 316: GitHub API GraphQL Batch Consolidation, ETag Caching & Token-Bucket Rate Optimization Research

**Issue**: [#316](https://github.com/dan-petty/devops-cli/issues/316)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/github`, `priority/p0-critical`

---

## 1. Description & Objectives

GitHub management is split between PyGithub and CLI `gh` subprocess calls, consuming excessive REST API quota through serial round-trips for issues, milestones, and pull requests.

#### Key Deliverables:
- Context & Rationale*: GitHub management is split between PyGithub and CLI `gh` subprocess calls, consuming excessive REST API quota through serial round-trips for issues, milestones, and pull requests.
- Deep Integration & Functional Extension*: Migrate high-frequency issue, pull request, milestone, and project board queries to pure GraphQL API operations; implement local RFC 7234 ETag caching (`If-None-Match`); native GitHub webhook signature verification and event dispatching.
- Code Optimization & Performance Acceleration*: Slash GitHub API quota consumption by 80%+ while reducing multi-item query latency from multiple seconds to a single round-trip; prevent rate-limit exhaustion during automated multi-repo reviews.
- Refactoring Potential & Legacy Elimination*: Consolidate the dual `PyGithub` and `run_gh` architectures into a single unified `GitHubClient` with integrated client-side token-bucket rate limiting; eliminate redundant issue/PR mapping helpers across `gh.py`, `pr.py`, and `projects.py`.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
