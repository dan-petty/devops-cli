# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for `open_or_update` in `tests/roadmap/steps/test_roadmap_step_open.py`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_open.py`
- [x] 1.2 Implement `find_open_pull` on `GitHubClient` in `src/devops_cli/github/client.py`
  - Verification: `$ uv run pytest tests/github/test_github_client.py`
- [x] 1.3 Implement `open_or_update` in `src/devops_cli/roadmap/steps/open.py`
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_step_open.py`
- [x] 1.4 Add CLI command `devops roadmap step open` in `src/devops_cli/commands/roadmap_step_open.py`
  - Verification: `$ uv run pytest tests/commands/test_roadmap_step_open.py`
- [x] 1.5 Update `stage.py` and `implement_run.py` to use `open_or_update`
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_scaffold.py`

## 2. Invariants and Documents

- [x] 2.1 Add architectural invariant test for `create_draft_pull` call sites
  - Verification: `$ uv run pytest tests/invariants/test_architectural_invariants.py -k test_every_draft_pull_creation_goes_through_open_step`
- [x] 2.2 Update documentation and verify OpenSpec check
  - Verification: `$ uv run devops openspec check && uv run devops docs check`
