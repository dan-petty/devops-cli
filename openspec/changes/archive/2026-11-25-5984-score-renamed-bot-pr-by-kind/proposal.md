# Proposal: #5984

## Why
`read_bot_pulls` reads `node.title` at report time, so a plan draft renamed to a delivery title loses its stage verdict, scores post-rename labels inconsistently, or drops timeline items past 100 events without failing. A `GitHubUnreadError` also aborts the Loki grade report, `"verdict/fix-plan"` is duplicated as raw literals, and docs still omit the full verdict label set or name `plan/needs-fix`.

## What Changes
- Request `RENAMED_TITLE_EVENT` (`previousTitle`) and `timelineItems.pageInfo { hasNextPage }` in `pr_verdict._SEARCH_QUERY`.
- Score each bot pull request by the title active when its first verdict label event occurred, and raise `GitHubUnreadError` with PR number and timeline page reason if `hasNextPage` is true.
- Catch `GitHubUnreadError` in `grade_report`, recording `GradeReport.verdict_error` and rendering `verdicts not read: <reason>` while preserving Loki rows.
- Define `FIX_PLAN_LABEL` once in `workflow_labels.py`, re-export it in `stage_verify.py`, and replace raw `"verdict/fix-plan"` literals in `pr_verdict.py`, `phase.py`, `workflow_labels.py`, and `failure.py`.
- Update ADR 0021 (`plan/needs-fix` -> `verdict/fix-plan`, list all six verdict labels) and `github_project_management.md` (list all six verdict labels).

## Capabilities
- `roadmap-job-grades`: Rename-aware verdict attribution, timeline overflow error, grade report error isolation, shared `FIX_PLAN_LABEL` constant, and verdict label documentation.

## Impact
- `src/devops_cli/roadmap/pr_verdict.py`
- `src/devops_cli/roadmap/job_grade_report.py`
- `src/devops_cli/lang/en/messages.py`
- `src/devops_cli/roadmap/workflow_labels.py`
- `src/devops_cli/roadmap/stage/stage_verify.py`
- `src/devops_cli/roadmap/phase.py`
- `src/devops_cli/roadmap/failure.py`
- `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`
- `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`

## Feasibility
Confirmed against `origin/main`: `pr_verdict.py:139,366` reads `node.title` and omits `RENAMED_TITLE_EVENT` and `timelineItems.pageInfo`; `job_grade_report.py:913` calls `_read_verdicts` without catching `GitHubUnreadError`; `pr_verdict.py:97`, `phase.py:275`, `workflow_labels.py:130`, and `failure.py:373` still hold literal `verdict/fix-plan`; ADR 0021 lines 60 and 215 use `plan/needs-fix`.

## Existing Tool Considered
PyGithub/PyGithub was rejected by ADR 0006. No external library replaces the project's custom GraphQL verdict scoring, Loki report isolation, and internal constant consolidation; extending `pr_verdict.py`, `job_grade_report.py`, and `workflow_labels.py` directly avoids extra dependencies.
