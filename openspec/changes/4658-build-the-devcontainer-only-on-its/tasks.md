# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: a new invariant reads `devcontainer-image.yml`, requires the schedule, the manual run and each file that `.devcontainer/Dockerfile` copies other than `src/`, and refuses a run for a change to `src/` only; the parity test of the pull request job reads the new workflow and finds no step filter; `ci.yml` has no `devcontainer` job; the job limit table names the new file
  - Verification: `$ uv run devops ci test tests/invariants/test_architectural_invariants.py tests/commands/test_ci.py tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Move the job to `.github/workflows/devcontainer-image.yml` with the `paths`, `schedule` and `workflow_dispatch` triggers, and remove the step filter
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 2. Documents

- [x] 2.1 State the new triggers in `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs`
