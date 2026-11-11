# Tasks

## 1. Stage before refine on the model lane
kind: behavior

- [x] 1.1 Write failing tests: the model lane order `retitle`, `stage`, `refine`, `alternatives`; a round with both rows due runs stage first; a refine that set an item Ready, also one that failed another item, writes `stage_due`, and stage is due in the next round; the dry run lists `stage` before `refine`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/stage/test_roadmap_stage_job.py tests/roadmap/test_roadmap_retitle.py`
- [x] 1.2 Reorder `MODEL_LANE_ROWS`, write `stage_due` from an outcome that set an item Ready, make stage due by the stamp, and delete `_stage_cross_job`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_job_rows.py tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_service.py tests/roadmap/implement/test_roadmap_implement_submit.py`

## 2. Documents
kind: documents

- [x] 2.1 State the new row order and the `stage_due` stamp in `k8s/README.md` and `docs/roadmap/intake.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4559 moves each stage item into its own Job, so a restart of the Service cannot stop a stage round.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
