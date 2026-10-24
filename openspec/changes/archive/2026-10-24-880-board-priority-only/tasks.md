# Tasks

## 1. Write failing unit tests

- [x] 1.1 Add offline tests in `tests/test_github_issues.py` verifying triage and status report board Priority via `InMemoryRoadmapStore` (`uv run pytest tests/test_github_issues.py`)
- [x] 1.2 Add offline test verifying an issue with a priority label but no board Priority field counts as unprioritized
- [x] 1.3 Add offline test verifying more than 100 open issues are all counted by triage and status
- [x] 1.4 Add offline test verifying a backlog item without a milestone is not flagged in triage

## 2. Refactor GitHub issues triage and status

- [x] 2.1 Refactor `audit_issues_triage` in `src/devops_cli/github/issues.py` to inspect board items and candidates via `RoadmapStore`
- [x] 2.2 Refactor `get_issues_summary` in `src/devops_cli/github/issues.py` to aggregate open issues by board Priority
- [x] 2.3 Update `issues_triage_cmd` and `issues_status_cmd` in `src/devops_cli/commands/gh.py` to pass store and display board priority

## 3. Remove Priority from field reconciliation

- [x] 3.1 Remove `_PRIORITY_LABELS` and `declared_priority` from `src/devops_cli/github/projects.py`
- [x] 3.2 Update `plan_item_changes` to plan only `Status` changes
- [x] 3.3 Update reconcile tests in `tests/test_github_projects_reconcile.py` and `tests/test_github_projects.py`

## 4. Documentation and label schema cleanup

- [x] 4.1 Remove `type/epic` and the four `priority/*` labels from `.github/labels.yml`
- [x] 4.2 Update `AGENTS.md`, `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, and task manuals to reference board Priority
- [x] 4.3 Remove deprecated priority label strings from all tests and fixtures so `git grep -En 'priority/(p[0-3]|high|medium|low)'` returns no matches

## 5. Verification and gate

- [x] 5.1 Run all tests and verify full pass (`uv run pytest`)
- [x] 5.2 Run CI gate (`uv run devops ci`)
- [x] 5.3 Archive change proposal (`uv run devops openspec archive 880-board-priority-only`)
