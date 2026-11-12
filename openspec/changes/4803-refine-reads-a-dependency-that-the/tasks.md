# Tasks

## 1. Behavior: refine and stage read a dependency named by its title

- [x] 1.1 Write failing tests: a title of an open or a closed issue is a dependency, a title that names no single issue fails the round with the check `dependencies`, quoted text that is no title fails nothing, and the stage job leaves out an item with an open dependency named by title
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_blocked.py tests/roadmap/refine/test_roadmap_refine_job_failure.py tests/roadmap/stage/test_roadmap_stage_selection.py`
- [x] 1.2 Add `title_dependencies`, add its issues to the validated proposal, add the job check `dependencies` with its message, and read the titles in the stage check `_dependency`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_blocked.py tests/roadmap/refine/test_roadmap_refine_job_failure.py tests/roadmap/stage/test_roadmap_stage_selection.py`

## 2. Documents

- [x] 2.1 Describe the title form of a dependency in `docs/roadmap/refine.md` and `docs/roadmap/stage.md`, and add the check `dependencies` to the job failures
  - Verification: `$ uv run devops ci docs`
