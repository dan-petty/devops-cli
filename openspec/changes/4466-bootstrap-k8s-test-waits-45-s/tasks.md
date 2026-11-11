# Tasks

## 1. Behavior

- [x] 1.1 Write failing test: the warning test and a default-timeout test assert `clock.waits`
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
- [x] 1.2 Route `_wait_for_docker_daemon` through the clock seam
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
