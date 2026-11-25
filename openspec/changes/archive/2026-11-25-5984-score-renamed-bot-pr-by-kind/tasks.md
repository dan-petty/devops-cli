# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for renamed PR verdicts, timeline overflow, grade report error isolation, `FIX_PLAN_LABEL` consistency, and verdict docs in `tests/roadmap/test_pr_verdict.py`, `tests/roadmap/test_job_grade_report.py`, and `tests/commands/test_roadmap_eval_grades.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_verdict.py tests/roadmap/test_job_grade_report.py tests/commands/test_roadmap_eval_grades.py`
- [x] 1.2 Implement rename-aware verdict scoring, timeline overflow guard, Loki isolation, and shared `FIX_PLAN_LABEL` across `pr_verdict.py`, `job_grade_report.py`, `messages.py`, `workflow_labels.py`, `stage_verify.py`, `phase.py`, and `failure.py`
  - Verification: `$ uv run devops ci test tests/roadmap/ tests/commands/test_roadmap_eval_grades.py tests/invariants/test_source_tree.py`

## 2. Documents

- [x] 2.1 Update ADR 0021 and `github_project_management.md` to name all six verdict labels and remove `plan/needs-fix` from current sections
  - Verification: `$ uv run devops openspec check && uv run devops ci docs`
