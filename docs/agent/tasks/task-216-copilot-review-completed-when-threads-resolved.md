# Task 216: Treat Copilot Review as Completed When Zero Unresolved Threads Remain

**Issue**: [#216](https://github.com/dan-petty/devops-cli/issues/216)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/github`

---

## 1. Description & Objectives

When GitHub Copilot completes an initial review and recommends changes, it posts a review body containing `### Changes recommended` and creates inline review discussion threads. After developers or AI agents remediate the comments, push new commits, reply to all threads, and programmatically resolve them, `devops pr check-readiness` correctly confirms 0 unresolved threads and clean mergeability.

However, `devops pr monitor` / `devops pr wait` inspects historical reviews via `_detect_copilot_status` and finds the original Copilot review with `Changes recommended`. Because Copilot is an AI bot that cannot approve or dismiss historical reviews, `copilot_status.state` remains permanently stuck in `changes_requested`, causing `_check_early_pr_failures` to exit with code 2 indefinitely even after 100% CI passes, 0 unresolved threads remain, and merge readiness is satisfied.

#### Key Deliverables:
1. **Copilot Resolved Thread Awareness ([`src/devops_cli/github/pr_monitor.py`](file:///workspaces/devops-cli/src/devops_cli/github/pr_monitor.py))**:
   - Update `_detect_copilot_status` to accept `unresolved_threads: list[ReviewThread] | None = None`.
   - When `has_changes` is True but `unresolved_threads` is empty (0 unresolved threads), transition `copilot_status.state` to `"completed"`.
   - Update `get_pr_monitoring_status` to fetch `unresolved_threads` and propagate to `_detect_copilot_status`.
   - Ensure `_resolve_review_decision` ignores bot reviews (e.g. Copilot) to prevent false human approval blocks.
2. **Submodule Unit Tests ([`tests/test_github_pr_monitor.py`](file:///workspaces/devops-cli/tests/test_github_pr_monitor.py))**:
   - Add unit test verifying that when Copilot recommended changes in body but 0 unresolved threads remain, `_detect_copilot_status` transitions to `completed`.
   - Add unit test verifying that when unresolved threads exist, `changes_requested` is retained.
   - Add integration test verifying `monitor_pr` exits code 0 when CI passes, Copilot recommended changes exist, and all review threads are resolved.
3. **Quality & Architectural Invariant Gates**:
   - Enforce cyclomatic complexity $\le 10$ and nesting depth $\le 5$.
   - 100% passing across all 10 CI quality gates (`uv run devops ci`).
