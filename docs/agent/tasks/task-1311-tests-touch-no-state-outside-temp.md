# Task: Tests Touch No State Outside Their Temporary Directories (#1311)

**Issue**: [#1311](https://github.com/dan-petty/devops-cli/issues/1311)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p0-critical
**Scope**: scope/ci

## Description
A test run wrote state outside its temporary directories, leaving artifacts in the developer's home (`.config/devops-cli/tls/`, `.local/share/devops-cli/worktrees/`, `.ssh/`, tool caches) and system temp (`devops_cli_ollama_rr_<uid>`, `devops-k8s-bootstrap.log`, `tmp*.out`). Home paths were fixed at import time, and the floor patched `CONST_USER_DATA_ROOT` and `CONFIG_PATH` rather than ensuring clean runtime isolation.

## Acceptance Criteria
- [x] Each pytest process (each xdist worker, or single process under `-n 0`) runs with an empty home under pytest's base temp, configured before devops-cli is imported, with git identity on `example.com`.
- [x] Writers write under test `tmp_path`:
  - [x] `tests/test_k8s.py` passes `--tls-dir`.
  - [x] `user_data_root()` resolves user data root honoring `DEVOPS_CLI_USER_DATA_ROOT` across `core/repo.py`, `git/worktree.py`, and `tools_lock`.
  - [x] `isolate_user_data_root` sets `DEVOPS_CLI_USER_DATA_ROOT` and drops the `CONST_USER_DATA_ROOT` patch.
  - [x] `tests/test_git_worktree.py` and `tests/test_review_worktree_regression.py` assert worktrees are under `tmp_path`.
  - [x] Ollama round-robin index lives under data directory (`DEVOPS_CLI_DATA_DIR`) and nowhere in temp directory; tested in `tests/test_ai_client_network.py`.
  - [x] `_ensure_known_host` accepts an optional `known_hosts` path so tests write under `tmp_path`.
- [x] `tempfile.gettempdir()` returns a directory under `tmp_path` during each test via `isolate_tempdir` fixture.
- [x] Floor patch of `config.settings.CONFIG_PATH` in `tests/conftest.py` is removed, and global config layer reads the worker's empty home.
- [x] Workspace tripwire fails when the run leaves state at `CONST_CONFIG_DIR`, `CONST_USER_DATA_ROOT`, `DEFAULT_SSH_KEY_DIR`, or `DEFAULT_LOCAL_BIN_DIR` in a worker's home, naming each leaked path.
- [x] Pytester test in `tests/test_isolation_tripwire.py` verifies a test writing under `CONST_CONFIG_DIR` fails the session naming the path.
- [x] Person-run check: running tests leaves no new entries under developer home or system temp.
- [x] `changelog.d/1311.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes with 100% compliance.

## Deliverables
- [x] Added `pytest_configure` hook in `tests/conftest.py` isolating `HOME` under pytest `basetemp` before `devops_cli` imports, initializing git identity on `example.com`, and recording worker homes.
- [x] Added `isolate_tempdir` autouse fixture in `tests/conftest.py` isolating `tempfile.tempdir` and temp environment variables to `tmp_path / "temp"`.
- [x] Removed `patch("devops_cli.config.settings.CONFIG_PATH", ...)` from `isolate_devops_cli_config`.
- [x] Removed `monkeypatch.setattr("...CONST_USER_DATA_ROOT", ...)` from `isolate_user_data_root`, setting `DEVOPS_CLI_USER_DATA_ROOT`.
- [x] Added `user_data_root()` helper in `src/devops_cli/core/repo.py` and updated `git/worktree.py`, `core/repo.py`, and `tools_lock`.
- [x] Updated Ollama round-robin index in `src/devops_cli/ai/client/network.py` to live under `DEVOPS_CLI_DATA_DIR`.
- [x] Updated `_ensure_known_host` in `src/devops_cli/git/operations.py` to accept `known_hosts`.
- [x] Updated Kubernetes and worktree tests to pass explicit `tmp_path` targets and assert path containment.
- [x] Extended workspace tripwire in `tests/conftest.py` to audit worker homes for leaks across `CONST_CONFIG_DIR`, `CONST_USER_DATA_ROOT`, `DEFAULT_SSH_KEY_DIR`, and `DEFAULT_LOCAL_BIN_DIR`.
- [x] Added unit and pytester regression tests in `tests/test_isolation_tripwire.py`.
- [x] Created changelog fragment `changelog.d/1311.md`.
