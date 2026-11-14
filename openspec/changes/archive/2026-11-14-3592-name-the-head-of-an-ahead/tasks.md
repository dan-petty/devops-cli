# Tasks

## 1. Name the commit that an ahead clone kept

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage.py`.

- [x] 1.1 Read the short hash and the subject of the clone's HEAD when the merge leaves another commit, and name them in `stage_clone_ahead`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage.py` passes
- [x] 1.2 Add the ahead case and the behind case to the new test module
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage.py` passes

## 2. Run the gates

Kind: other. Reads: `tests/roadmap/stage/`. Changes: none.

- [x] 2.1 Run the gate of the branch
  - Verification: `$ uv run devops ci test tests/roadmap/stage` passes
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
