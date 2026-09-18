# Task 258: Add Integrations to Keep GitHub Pull Requests Up to Date

**Issue**: [#258](https://github.com/dan-petty/devops-cli/issues/258)
**PR**: [#259](https://github.com/dan-petty/devops-cli/pull/259)
**Status**: Closed (Merged in PR #259)
**Milestone**: `v0.2.20`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Objectives

Implement end-to-end automated integrations and developer tooling to keep GitHub pull requests synchronized with their base branches (e.g., `main` or active release branches), preventing out-of-date branch drift and CI failures due to stale target branches.

#### Key Deliverables:
- [x] 1. Implement CLI subcommand `devops pr update [PR_NUMBER]` with `--all`, `--base`, `--repo`, `--expected-head-sha`, and `--dry-run` options using GitHub's `PUT /repos/{owner}/{repo}/pulls/{pull_number}/update-branch` API.
- [x] 2. Implement FastMCP tool `pr_update_branch` in `src/devops_cli/ai/mcp/server.py` allowing autonomous AI agents to keep PRs updated programmatically.
- [x] 3. Create GitHub Actions workflow `.github/workflows/update-prs.yml` triggering automatically on base branch push (`main`, `release/**`), manual `workflow_dispatch`, and `/update` / `/sync` PR comments.
- [x] 4. Add internationalized help and message strings in `src/devops_cli/lang/en/help.py` and `src/devops_cli/lang/en/messages.py`.
- [x] 5. Author comprehensive test suite in `tests/test_pr_update.py` verifying single PR update, batch `--all` updates, conflict handling (HTTP 422), `--dry-run`, and MCP tool wrapper with structural tuple assertions.
- [x] 6. Ensure strict compliance with $M \le 10$, max depth $\le 5$, zero secret/internal LAN leaks, and 100% passing across all 10 CI quality gates (`uv run devops ci`).

---

## 2. Verification Results

- **Unit & Integration Tests**: `pytest tests/test_pr_update.py` passed 10/10 tests.
- **Actionlint**: `devops ci actionlint` passed cleanly on `.github/workflows/update-prs.yml`.
- **Architectural Invariants**: `pytest tests/test_architectural_invariants.py` passed 8/8 tests ($M \le 10$, max depth $\le 5$).
- **Live CLI Simulation**: `devops pr update 257 --dry-run` and `devops pr update --all --dry-run` accurately resolve base/head branches and render formatted tables.
