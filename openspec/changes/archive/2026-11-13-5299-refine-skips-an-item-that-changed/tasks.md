# Tasks

## 1. The skip of a changed item (behavior)

- [x] 1.1 Write failing tests: a write that the change of the item refuses gives no result line and no `RoadmapRefineError`; another failure of the write still raises and logs `error`; a person who moves the item during the round gets no write, one INFO line and a new read in the next round; a body edit during the round logs no result line and counts the item as not written
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_round.py`
- [x] 1.2 Catch `RoadmapItemChangedError` in `RefineWriter.settle`, give `RefineApplied` the count `changed_count`, return it from the body check of `_apply_refined`, and write no result line for a changed item
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_round.py tests/roadmap/refine/test_roadmap_refine_one_write.py`

## 2. Documents

- [x] 2.1 Say in `docs/roadmap/job-success.md` that a changed refine item writes no line, and in `docs/ROADMAP_WORKFLOW.md` that refine skips it
  - Verification: `$ uv run devops ci docs`
