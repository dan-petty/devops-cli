# Task 519: Dashboard Refresh Races Panel Mounting and Fails the Worker

**Issue**: [#519](https://github.com/dan-petty/devops-cli/issues/519)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/bug, scope/cli

---

## 1. Description & Objectives

During interactive dashboard execution or parallel test runs (`tests/test_ui_dashboard.py::test_textual_dashboard_app_lifecycle`), worker threads fetching domain snapshot updates could execute and call `apply_snapshot` / `panel.apply(...)` before panels or their child `Static` / `DataTable` widgets were composed and mounted. In Textual, querying for unmounted child nodes (`self.query_one(Static)`) raises `NoMatches`. When caught in `apply_snapshot`, the error fallback also attempted to query the unmounted widget and re-raised `NoMatches`, causing `WorkerFailed` exceptions.

This deliverable:
- Defensively guards all domain panels (`DomainPanel`, `K8sPanel`, `DockerPanel`, `ReviewPanel`) in `src/devops_cli/ui/widgets.py` by deferring snapshot application (`_pending_snapshot`) when the panel is unmounted (`not self.is_mounted`) or when child queries raise `NoMatches`.
- Applies any pending deferred snapshot upon widget mount (`on_mount`).
- Defends `apply_snapshot` in `src/devops_cli/ui/dashboard.py` against calls when the app is not running or screens are not yet mounted (`ScreenStackError`), and suppresses secondary exceptions in the error fallback.
- Adds comprehensive test coverage in `tests/test_ui_dashboard.py` verifying that driving snapshot updates before mounting defers cleanly and does not fail any workers.

---

## 2. Acceptance Criteria

- [x] A panel update before the panel is mounted is deferred or dropped, never an exception.
- [x] A test drives a refresh before mount and asserts no worker failure.
- [x] Changelog fragment `changelog.d/519.md` authored.
- [x] Gated CI quality checks pass in `uv run devops ci`.

---

## 3. Deliverables

- [x] `src/devops_cli/ui/widgets.py`: Defer updates when unmounted and catch `NoMatches` across all panels.
- [x] `src/devops_cli/ui/dashboard.py`: Guard `apply_snapshot` against unmounted app/screen state and protect fallback.
- [x] `tests/test_ui_dashboard.py`: Added `test_dashboard_refresh_before_mount_does_not_fail_worker`.
- [x] `changelog.d/519.md`: Changelog entry.
- [x] `docs/agent/tasks/task-519-dashboard-refresh-races-panel-mounting.md`: Task documentation.
