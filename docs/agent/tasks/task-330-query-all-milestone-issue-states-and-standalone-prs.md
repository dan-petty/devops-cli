# Task 330: Query All Milestone Issue States and Standalone PRs for Release PR Deliverables

**Issue**: [#330](https://github.com/dan-petty/devops-cli/issues/330)
**Status**: Done
**Milestone**: `v0.2.21`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/release`, `priority/p1-high`

---

## 1. Description & Objectives

When executing `devops release pr`, the milestone deliverables query `_query_gh_milestone_issues` defaulted to `--state open` by invoking `gh issue list --milestone <tag>` without `--state all`. Consequently, all completed/closed milestone issues were omitted from the PR description's `### Included Deliverables` section, leaving only open epics. Additionally, standalone milestone pull requests (such as #292) and milestone assignment (`--milestone`) were missing from `_build_release_pr_command`.

#### Key Deliverables:
- [x] Context & Rationale: Ensure release PR descriptions capture all milestone issues regardless of state (open/closed) and standalone PRs.
- [x] Deep Integration & Functional Extension: Update `_fetch_raw_milestone_issue_numbers` to specify `--state all` with limit 100; add `_fetch_raw_milestone_pr_numbers` to discover standalone milestone PRs while deduplicating referenced closed issues.
- [x] CLI & Subcommand Optimization: Pass `--milestone` to `_build_release_pr_command` with graceful fallback handling in `_execute_release_pr`.
- [x] Refactoring Potential & Complexity Reduction: Decompose `_execute_release_pr` into `_strip_pr_cmd_flag` and `_build_pr_fallback_cmd` maintaining cyclomatic complexity $M \le 10$.
- [x] Unit and integration test coverage with structural tuple equality assertions (`tests/test_release.py`).
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
