# Tasks

## 1. Behavior: the stage hold and the record for onboarding

- [x] 1.1 Add the failing tests: a stage round in a repository without `openspec/config.yaml` pushes no branch, calls no model, counts and logs the hold, and returns the file in its outcome; a named item is held and the plan names the file; a repository with the file names no missing file; `explain` prints the reason; the dry runs list the read; a round reads the change folders once and the config file once
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job.py tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_dry_runs.py`
- [x] 1.2 Add `uses_openspec` in `src/devops_cli/openspec/project.py`, the `no_openspec` rule of the stage selection, `StagePlan.missing`, `JobOutcome.missing`, the message of the reason and the read in the dry runs of `stage` and `explain`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job.py tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/stage/test_roadmap_stage_planned.py`

## 2. Documents

- [x] 2.1 Describe the hold in `docs/roadmap/stage.md` and in `docs/roadmap/onboard.md`, and regenerate the documentation for the new message
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4664 adds the onboarding row that reads `JobOutcome.missing`.
- #3770 adds `openspec/config.yaml` to a repository through onboarding. The hold of a repository ends when that pull request merges.
- Pending a person: close the 9 open draft plan pull requests after the rollout (owner decision 2). The pull request comment gives the steps.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
