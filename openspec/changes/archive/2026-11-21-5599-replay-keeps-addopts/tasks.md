# Tasks

## 1. Behavior

- [x] 1.1 A test that reads `addopts` and the number of workers fails in the replay, which clears `addopts`
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`
- [x] 1.2 The replay gives `-n 0` in place of `-o addopts=`, so it keeps `addopts` and starts no worker
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py`

## 2. Documents

- [x] 2.1 The docstring of `fail_to_pass.py` and the comment of `CONST_FAIL_TO_PASS_PYTEST_FLAGS` name `-n 0` and say that the replay keeps `addopts`
  - Verification: `$ uv run devops ci docs`
