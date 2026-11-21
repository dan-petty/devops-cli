# Tasks

## 1. The plan commit on the phases

Kind: behavior.

- [x] 1.1 Write failing tests: a push URL in the clone of the job changes nothing; the orphan cleanup keeps the mark of a kept branch; the round after the cleanup of the Service resumes on the kept branch
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scaffold.py`
- [x] 1.2 Push the plan with `stage_phases.push_plan`, delete the worktree push, and keep `stage.pending` of a kept branch
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## 2. Documents

Kind: other.

- [x] 2.1 Describe the push of the plan in `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`
