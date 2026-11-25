# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for older-rules blocked wait ending, current-rules blocked wait holding, and real open dependency remaining blocked (`tests/roadmap/refine/test_roadmap_refine_person_wait.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py`
- [x] 1.2 Apply `_set_by_older_rules` to `NextStep.BLOCKED` waits in `_wait_still_on` (`src/devops_cli/roadmap/refine/refine.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/refine.md` and validate OpenSpec and docs checks
  - Verification: `$ uv run devops openspec check`
