# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: a fix of a prompt, pins, the knowledge base or files outside src passes with no replay; a behavior group that changes only a prompt is refused
  - Verification: `$ uv run pytest tests/ci/test_fail_to_pass.py tests/roadmap/stage/test_roadmap_stage_kind.py -q`
- [x] 1.2 Add `is_source_code`, `needs_proof` and the stage rule
  - Verification: `$ uv run pytest tests/ci/test_fail_to_pass.py tests/roadmap/stage/test_roadmap_stage_kind.py -q`

## 2. Workflow and documents

- [x] 2.1 Narrow the workflow path filter to `src/**/*.py`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 2.2 State the rule in docs/TESTING.md and the stage prompts
  - Verification: `$ uv run devops ci docs`
