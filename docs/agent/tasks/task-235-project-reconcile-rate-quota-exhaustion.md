# Task 235: Project Reconcile Rate Quota Exhaustion and Unbounded Candidate Mutations

**Issue**: [#235](https://github.com/dan-petty/devops-cli/issues/235)
**PR**: [#236](https://github.com/dan-petty/devops-cli/pull/236)
**Status**: Completed
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/github`, `scope/cli`

---

## 1. Description & Objectives

When executing `devops gh project reconcile --project-number 2`, the command consumed thousands of GitHub GraphQL requests within minutes, exhausting almost the entire GraphQL request quota (dropping from 5,000 to 84 remaining).

This task hardens project reconciliation and GitHub rate limiting against runaway quota consumption:

1. **Raise GraphQL Safety Threshold (`devops_cli.config.defaults`)**:
   - Elevate `DEFAULT_GH_GRAPHQL_SAFETY_THRESHOLD` from `100` (2%) to `500` (or 20% of limit) so operations halt well before critical exhaustion.
   - Define `DEFAULT_GH_MAX_TOTAL_MUTATIONS_PER_RECONCILE = 25` as the hard aggregate cap on total GraphQL mutations per reconciliation cycle.

2. **Owner Resolution Caching & Redundant Fallback Elimination (`devops_cli.github.projects`)**:
   - Cache resolved project owner arguments in `_PROJECT_OWNER_ARG_CACHE` so once `--owner @me` succeeds for a user account, subsequent calls do not repeat the failing `--owner <username>` call.

3. **Board-First Reconciliation & Open Candidates Filtering (`devops_cli.github.projects`)**:
   - Reconcile custom fields on items already present on the board (`items_data`).
   - Restrict candidate provisioning to open issues (`state="open"`) and open PRs rather than scanning all closed historical issues.
   - Enforce the aggregate mutation budget across both provisioning and custom field updates.

4. **Rate Limiter Attribution & Tracking (`devops_cli.github.rate_limiter`)**:
   - Ensure all `gh project` subcommands are attributed to `"graphql"` and properly estimate/record token consumption.

---

## 2. Key Deliverables

- `src/devops_cli/config/defaults.py`: Elevated GraphQL safety threshold and aggregate mutation cap constant.
- `src/devops_cli/github/projects.py`: Owner resolution cache, open candidate filtering, and aggregate mutation budget enforcement.
- `src/devops_cli/github/rate_limiter.py`: Accurate GraphQL resource attribution and token utilization tracking.
- `tests/test_github_projects_reconcile.py`: Targeted unit tests asserting aggregate mutation budget, open candidate filtering, and owner argument caching.
