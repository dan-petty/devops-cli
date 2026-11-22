# Tasks

## 1. The plan commit on the phases

Kind: behavior.

- [x] 1.1 Write failing tests: a push URL in the clone of the job changes nothing; a re-stage of the same plan refuses a branch that moved past the recorded commit; a refused draft deletes the pushed branch where the push went; the stage dry-run plan pushes from a new repository
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scaffold.py tests/roadmap/stage/test_roadmap_stage_restage.py tests/roadmap/test_roadmap_dry_runs.py`
- [x] 1.2 Push the plan with `stage_phases.push_plan`, delete the branch of a refused draft with `delete_plan_branch`, and delete the worktree push and the `base` of `add_worktree`
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## 2. Documents

Kind: other.

- [x] 2.1 Describe the push of the plan in `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`
