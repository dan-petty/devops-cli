# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the #1643 invariant accepts the image that a needed job exports and the shard loads, and fails on a shard build; the workflow shape test reads the build job, the artifact steps, `-rs`, `--durations=10` and the empty tooling cache paths; `setup-toolchain` skips the cache step on empty paths; the build job has a limit
  - Verification: `$ uv run devops ci test tests/invariants/test_architectural_invariants.py tests/commands/test_ci.py tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Add the `service-image-build` job, load its artifact in each shard, add the pytest options, and skip the tooling cache on empty paths
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 2. Documents

- [x] 2.1 State the build job in `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs`
