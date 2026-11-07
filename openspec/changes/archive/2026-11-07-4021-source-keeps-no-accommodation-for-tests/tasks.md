# Tasks

## 1. The async runner goes through the process runner (behavior)

- [x] 1.1 Add failing tests: an async start is answered by the active runner while `subprocess.run` is replaced, and an async start in a dry run plans the command
  - Verification: `$ uv run devops ci test tests/core/test_process_async_runner.py`
- [x] 1.2 Make `run_subprocess_async` call the active runner, delete its copy of the runner body and both checks of `subprocess.run`, and delete `PYTEST_CURRENT_TEST` from the environment allow-list
  - Verification: `$ uv run devops ci test tests/core/test_process_async_runner.py tests/core/test_process.py`
- [x] 1.3 Move the four `devops ci` tests that replaced `subprocess.run` to `process_fake`
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/commands/test_ci_dry_run.py`

## 2. Tests set the config through fixtures (refactor)

- [x] 2.1 Take the config path out of the settings cache key
  - Verification: `$ uv run devops ci test tests/config/test_settings_cache.py`
- [x] 2.2 Move the ten sites that rebound `CONFIG_PATH` to the `config` fixture, the `global_config` fixture or the floor's config file
  - Verification: `! git grep -nF 'CONFIG_PATH"' tests/`

## 3. Repository state has public seams (behavior)

- [x] 3.1 Add a test that `reset_repo_caches` makes the origin lookup read the remote again, delete the hand-attached `cache_clear` of `get_repo_origin_name`, and call `reset_repo_caches` in the test that changes a remote
  - Verification: `$ uv run devops ci test tests/commands/test_repos.py`
- [x] 3.2 Add `install_own_source_dir` with its reset in `reset_repo_caches`, install it in the floor, and use it in the three review tests in place of a patch of `_own_source_dir`
  - Verification: `$ uv run devops ci test tests/review/test_review_untrusted_tree.py tests/invariants/test_hermetic_floor.py`
- [x] 3.3 Set `HOME` in `test_ensure_known_host` in place of a patch of `Path.home`
  - Verification: `$ uv run devops ci test tests/git/test_git_operations.py`

## 4. The checks fail if the problems return (behavior)

- [x] 4.1 Add the invariant tests: no check of the identity of `subprocess.run` in `src/`, and a ceiling on the reads of `PYTEST_CURRENT_TEST`
  - Verification: `$ uv run devops ci test tests/invariants/test_source_tree.py`

## 5. Documents

- [x] 5.1 Describe the own-source seam and the new checks in `docs/TESTING.md`, and drop the pass-through from the plan of change `1325-ci-commands-edge-fakes`
  - Verification: `uv run devops openspec check`

## 6. Archive

- [x] 6.1 Archive the change
  - Verification: `uv run devops openspec archive 4021-source-keeps-no-accommodation-for-tests`
