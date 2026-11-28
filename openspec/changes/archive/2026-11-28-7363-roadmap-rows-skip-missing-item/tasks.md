# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests covering all remaining roadmap rows (`implement`, `stage`, `watch`, `open`, `refine`, `retitle`, `fix-plan`, `intake`, `metrics`), typed error classes in `implement_submit` and `return_item`, narrowed `plan_drift` with orphan PR closure, GraphQL timeline drop, and 301 repository name read
  - Verification: `$ UV_COMPILE_BYTECODE=0 uv run devops ci test tests/roadmap/test_roadmap_other_rows_item_left.py tests/roadmap/stage/test_roadmap_stage_drift.py tests/github/test_github_client_issue_reads.py`
- [x] 1.2 Implement `GitHubNotAnIssueError` handling, GraphQL timeline record drops, typed submit/return errors, and `plan_drift` orphan PR close
  - Verification: `$ UV_COMPILE_BYTECODE=0 uv run devops ci test tests/roadmap/test_roadmap_other_rows_item_left.py tests/roadmap/stage/test_roadmap_stage_drift.py tests/github/test_github_client_issue_reads.py tests/roadmap/test_roadmap_rows_issue_answer.py tests/roadmap/test_roadmap_return.py`

## 2. Documents and Quality Gate

- [x] 2.1 Validate OpenSpec artifacts, docs, mypy, and static CI checks
  - Verification: `$ UV_COMPILE_BYTECODE=0 uv run devops openspec check && UV_COMPILE_BYTECODE=0 uv run devops ci docs && UV_COMPILE_BYTECODE=0 uv run devops ci --check --only lint,format,domain,test-tree,constructs,startup-imports,swallowed-failures`
