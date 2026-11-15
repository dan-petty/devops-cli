# Tasks: #5499

## 1. GitHub git refs API client method
<!-- kind: behavior -->
- [x] 1.1 Add tests for `create_ref` on `GitHubClient`
  Verification: `$ uv run pytest tests/github/test_client_git_refs.py`
- [x] 1.2 Implement `create_ref` on `GitHubClient` using `POST /repos/{owner}/{repo}/git/refs`
  Verification: `$ uv run pytest tests/github/test_client_git_refs.py`

## 2. Scaffold step and four resume cases
<!-- kind: behavior -->
- [x] 2.1 Add tests for scaffold step four resume rules (`created`, `resumed`, `adopted`, `held`), `--dry-run`, ref creation with no commit, and structural test
  Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_scaffold.py`
- [x] 2.2 Implement `src/devops_cli/roadmap/steps/scaffold.py`, `ScaffoldRecordKey`, and `RoadmapJob.SCAFFOLD`
  Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_scaffold.py`

## 3. Scaffold CLI command
<!-- kind: behavior -->
- [x] 3.1 Add CLI tests for `devops roadmap step scaffold`
  Verification: `$ uv run pytest tests/commands/test_roadmap_step_scaffold.py`
- [x] 3.2 Implement `devops roadmap step scaffold` in `src/devops_cli/commands/roadmap_step_scaffold.py` and register in `src/devops_cli/commands/roadmap_step.py`
  Verification: `$ uv run pytest tests/commands/test_roadmap_step_scaffold.py`

## 4. Stage job integration and orphan branch preservation
<!-- kind: behavior -->
- [x] 4.1 Add tests for keeping App-only branch of Ready item and killed stage round resuming with 0 planner calls
  Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_scaffold.py tests/roadmap/stage/test_roadmap_stage_orphan.py`
- [x] 4.2 Update `_orphans` in `stage.py` and integrate scaffold in `stage_job.py` and `stage_submit.py`
  Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_scaffold.py tests/roadmap/stage/test_roadmap_stage_orphan.py`

## 5. Documentation
<!-- kind: documents -->
- [x] 5.1 Update `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md` to state resume rules
  Verification: `$ uv run pytest tests/roadmap/test_roadmap_scaffold_docs.py`
- [x] 5.2 Regenerate CLI documentation with `devops docs generate`
  Verification: `$ uv run devops docs generate && uv run devops ci docs`

## Workflow follow-up
- Follow-up issue #5518 adds kind `delivery`.
- Follow-up issue #5533 adds candidate branches.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: after release, run stage row as App on next Ready items and post result lines.
