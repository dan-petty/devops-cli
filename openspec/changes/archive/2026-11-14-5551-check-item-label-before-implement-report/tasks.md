# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for implement runner Job item label check
  - Verification: `$ uv run pytest -k "test_a_record_naming_another_items_job_is_skipped_and_reads_no_log" tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 1.2 Implement item label check in `_report_ended` in `src/devops_cli/roadmap/implement/implement_submit.py`
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_submit.py`

## 2. Documents

- [x] 2.1 Update documentation and check quality gates
  - Verification: `$ uv run devops ci --only lint,format,typecheck,docs`
