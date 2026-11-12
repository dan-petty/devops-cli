# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: a person wait that older rules set gets one new look on an unchanged body; a wait that the current rules set gets none
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py`
- [x] 1.2 Add `CONST_ROADMAP_REFINE_RULES_SINCE` and `RefineRecordKey.RULES`; record the version with each written proposal; end a person wait that older rules set
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/refine.md` and the job record table of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`
