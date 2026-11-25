# Tasks

## 1. Behavior

- [x] 1.1 Write failing ADR index context tests (`tests/roadmap/refine/test_roadmap_refine_context.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_context.py`
- [x] 1.2 Replace full ADR files with a sorted in-force index in `collect_context` (`src/devops_cli/roadmap/refine/refine.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_context.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec changes and project gates after implementation
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

Work deferred from the design into #7005 stays out of this pull request.
Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
