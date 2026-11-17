# Tasks

## 1. Implement group title placeholder checks and shared helper

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `tests/roadmap/stage/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_draft_readiness.py`, `tests/roadmap/stage/test_roadmap_stage_ready.py`.

- [x] 1.1 Write tests that prove `x` fails on the base, build a StageProposal and assert that content_problems returns no problem for a valid plan, and returns a problem for a placeholder group title
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_title.py`
- [x] 1.2 Write tests for draft_readiness and stage_ready refusing placeholder group titles and reading tasks.md at head
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py tests/roadmap/stage/test_roadmap_stage_ready.py`
- [x] 1.3 Implement group_title_problems in stage_change.py, call it in content_problems, and update draft_readiness and stage_ready
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_title.py tests/roadmap/test_roadmap_draft_readiness.py tests/roadmap/stage/test_roadmap_stage_ready.py`
