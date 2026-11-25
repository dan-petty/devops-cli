# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for ADR option subject parsing, false-rejection replays, own-repository precedence, and ADR 0018 preservation
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives_project_facts.py`
- [x] 1.2 Implement subject-aware `rejects()` in `src/devops_cli/roadmap/adr.py` and own-repository precedence in `src/devops_cli/roadmap/alternatives.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives_project_facts.py tests/roadmap/test_roadmap_alternatives.py`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/alternatives.md` with the ADR rejection subject and own-repository rules
  - Verification: `$ uv run devops ci docs`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
