# Task: Tests Never Write to the Project Config, Data or Tracked Files (#749)

**Issue**: [#749](https://github.com/dan-petty/devops-cli/issues/749)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/ci

## Description
Tests sometimes mutated the maintainer's `config.yaml` values and wrote into the real `.data` directory. Previous isolation was partial: `isolate_data_dir` pointed `DEVOPS_CLI_DATA_DIR` at a temporary directory per-test, but `save_settings` relied on a test-only `PYTEST_CURRENT_TEST` check with hardcoded workspace paths. Settings cached before per-test fixtures ran could still resolve and write to the real files. During parallel test runs, `CHANGELOG.md` briefly disappeared and `.git/index.lock` was left behind.

## Acceptance Criteria
- [x] A session-level tripwire snapshots `config.yaml` and git-tracked files, while explicit test path checks ensure test paths are strictly outside the project directory and forbidden test artifacts are not left behind.
- [x] The tripwire runs once on the pytest-xdist controller process so parallel workers do not race.
- [x] Every test receives an isolated temporary config via `DEVOPS_CLI_CONFIG` backed by `tmp_path`.
- [x] Test-only branches and hardcoded workspace paths are removed from `save_settings`.
- [x] All test suite leaks detected by the tripwire are remediated.
- [x] All 10 CI quality gates pass with 100% compliance.

## Deliverables
- [x] Session-level workspace tripwire in `tests/conftest.py` with `pytest_sessionstart`, `pytest_sessionfinish`, and `pytest_terminal_summary`.
- [x] Per-test `isolate_devops_cli_config` fixture in `tests/conftest.py` supplying `DEVOPS_CLI_CONFIG` via `tmp_path` and clearing settings cache.
- [x] Per-test `verify_test_paths_isolated` fixture ensuring active test environment paths reside outside the repository.
- [x] Settings cache invalidation on `isolate_data_dir` setup and teardown.
- [x] Cleaned up `save_settings` in `src/devops_cli/config/settings.py` removing `PYTEST_CURRENT_TEST` check.
- [x] Comprehensive unit tests in `tests/test_isolation_tripwire.py`.
