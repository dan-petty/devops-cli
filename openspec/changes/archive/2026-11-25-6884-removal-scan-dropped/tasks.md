# Tasks

## 1. Behavior

<!-- kind: behavior -->

- [x] 1.1 Update and add failing tests in `tests/roadmap/stage/test_roadmap_stage_removal_references.py` covering `drop`/`drops`/`dropped`/`dropping` exclusion, `deletes` unhandled test references, and active keyword filtering
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`
- [x] 1.2 Remove `drop`, `drops`, `dropped`, and `dropping` from `REMOVAL_VERBS` in `src/devops_cli/roadmap/stage/stage_removal_references.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`
