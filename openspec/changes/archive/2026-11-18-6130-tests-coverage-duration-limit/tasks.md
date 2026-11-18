# Tasks

## 1. Refresh Durations and Add Shard

- [x] 1.1 Refresh recorded module durations
  - Verification: `$ uv run devops ci durations`
- [x] 1.2 Add fifth shard to CI workflow matrix
  - Verification: `$ uv run pytest tests/commands/test_ci_shard.py`

## 2. Documentation

- [x] 2.1 Update documentation in docs/SDLC.md and docs/TESTING.md
  - Verification: `$ uv run devops ci docs`
