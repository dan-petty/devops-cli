# Task: PR Monitor Reports Copilot as Idle or Completed When Its Timeline or Reviews Read Fails (#806)

**Issue**: [#806](https://github.com/dan-petty/devops-cli/issues/806)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/github, type/bug

## Description

`devops pr monitor` previously reported that GitHub Copilot was idle or completed review when timeline or review reads failed (due to rate limiting, network blips, or non-zero subprocess exit), potentially certifying a PR ready while Copilot was still reviewing or had requested changes.

This implementation adds fail-closed Copilot review state handling:
- **`CopilotReviewStatus` Model**: Added `unread` state and `unread_reason: str = ""` field.
- **Timeline & Reviews Read Failure Detection**:
  - `_extract_proc_error`: Trimmed stderr (up to 256 chars) or `Exit code {code}` fallback.
  - `_query_timeline_copilot_state`: Returns `(working, event, err)`, capturing subprocess failures.
  - `_fetch_raw_reviews`: Returns `RawReviewsList` preserving review items and tracking `error` reason upon non-zero exit.
  - `_detect_copilot_status`: Detects read failures from timeline or reviews and immediately returns `unread` state with the failure reason, taking precedence over `changes_requested` and `completed`.
- **Readiness & Settle Gating**:
  - `PRMonitorStatus.is_review_ready` treats `unread` Copilot state as not ready.
  - `_check_pr_ready_step` avoids certifying settled readiness while Copilot is `unread`.
  - `_build_monitor_timeout_result` reports `(Copilot review state could not be read: {reason})` upon timeout.
  - `_build_failure_reasons` includes `Copilot review state could not be read: {reason}` in failure reasons.
  - `devops pr monitor --format json` emits `state: unread` and `unread_reason` in structured payload.

## Acceptance Criteria

- [x] Timeline read exits 1 and an earlier Copilot review exists: `_detect_copilot_status` returns `state == "unread"` with non-empty `unread_reason`, and `PRMonitorStatus.is_review_ready` is `False`.
- [x] Reviews read exits 1: `get_pr_monitoring_status` returns `copilot_status.state == "unread"`.
- [x] Timeline read exits 1 and known Copilot review recommends changes: state is `unread`, taking precedence over `changes_requested`.
- [x] A successful read with empty output still reports `idle`, and every existing state is unchanged.
- [x] `monitor_pr` does not certify an approved, green PR ready while Copilot is `unread`, exiting 3 with the unread reason in the timeout message.
- [x] `failure_reasons` names the unread reason.
- [x] `devops pr monitor --format json` output carries `copilot_status.state == "unread"` and `copilot_status.unread_reason`.
- [x] All tests run offline and patch external subprocess calls.
- [x] `changelog.d/806.md` exists and `CHANGELOG.md` and `docs/ROADMAP.md` remain untouched.
- Pending a person: `uv run devops ci` passes on this branch.
