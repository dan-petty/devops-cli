# Tasks

## 1. Behavior

- [x] 1.1 Write a failing test: the workflow shape test asks for `-r` with the shard summary characters `fEs` in the shard test step
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py`
- [x] 1.2 Give pytest `-rfEs` in place of `-rs` in the shard test step of the Service Image Tests workflow
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py`

## 2. Workflows

- [x] 2.1 Lint the changed workflow
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 3. Documents

- [x] 3.1 Say in docs/SDLC.md that each Service image shard names each failed test
  - Verification: `$ uv run devops ci docs`
