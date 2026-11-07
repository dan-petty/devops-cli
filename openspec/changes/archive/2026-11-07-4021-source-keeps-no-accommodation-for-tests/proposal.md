# Proposal

## Why

Issue #4021 is item 6 of the Fit note of #1333. Product code in `src/devops_cli` still holds hooks that only tests use, and some tests rebind module state to reach them.

- The async runner starts the sync path when a test has replaced `subprocess.run`. The module function `run_subprocess_async` is also a second copy of `DefaultProcessRunner.run_async`. It does not call `get_process_runner()`, so `process_fake` cannot answer it.
- The allow-list of the child-process environment passes `PYTEST_CURRENT_TEST`.
- The settings cache key holds the config path, because tests rebind `CONFIG_PATH`. Ten test sites in nine files do so.
- `get_repo_origin_name.cache_clear` is attached by hand, and a test calls it.
- The floor and three review tests patch the private `core.repo._own_source_dir`.
- `test_ensure_known_host` patches `pathlib.Path.home`.

## What Changes

- `run_subprocess_async` calls `get_process_runner().run_async`. Its copy of the runner body goes. The `__module__` check of `subprocess.run` goes from both async paths. In a dry run, the module function now returns the planned result that the runner returns, in place of printing the command and then starting it.
- `PYTEST_CURRENT_TEST` leaves the allow-list of `core/process.py`.
- `_config_layers` builds its cache key from the project config variable, the working directory and the trust of the tree. The global config path is no part of it. The ten test sites that rebound `CONFIG_PATH` use the `config` fixture, the `global_config` fixture or the floor's own config file.
- The hand-attached `cache_clear` goes. `reset_repo_caches` is the public reset of the origin cache, and the floor already calls it. A test that changes a remote calls it.
- `core/repo.py` gets `install_own_source_dir`, a public seam of the directory that devops-cli's package runs from. The floor installs a directory in site-packages before each test. `reset_own_source_dir` removes it, and the floor calls it after each test. `reset_repo_caches` keeps it. The floor fixture and the three review tests use the seam in place of a patch of `_own_source_dir`.
- `test_ensure_known_host` sets `HOME` through the environment.
- Tests: `tests/core/test_process_async_runner.py` is new. Four `devops ci` tests that replaced `subprocess.run` use `process_fake`. `tests/invariants/test_source_tree.py` fails on a check of `subprocess.run`'s identity in `src/` and on a rise in the reads of `PYTEST_CURRENT_TEST`.
- Not in this change, and left for the other items of #1333: the two reads of `PYTEST_CURRENT_TEST` in `commands/ci.py`, and the GitHub token privates (`_github_token`, `_lookup_github_token`) that the floor assigns. The Feasibility table gives the reason for each.
- This change alters no behavior a consumer observes, except that a dry run of an async start no longer starts the program. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request: about 25 files, and one concern, the module state that tests reach.

## Impact

- `src/devops_cli/core/process.py`, `src/devops_cli/core/repo.py`, `src/devops_cli/config/settings.py`.
- `tests/conftest.py`, `tests/core/test_process_async_runner.py` (new), `tests/invariants/test_source_tree.py`, and the test files that rebound `CONFIG_PATH`, replaced `subprocess.run` or patched `_own_source_dir` or `Path.home`.
- `docs/TESTING.md`, and the plan of the stale change `1325-ci-commands-edge-fakes`, which named the pass-through as its work.

## Feasibility

Checked on `origin/main` 226394ca, 2026-11-07. The issue text of #1333 was written at v0.2.28, so each requirement was read again against the tree and the table gives the result.

| Requirement | State today | Action |
| :--- | :--- | :--- |
| Async reroute removed | Not done. `rg -n "__module__" src/devops_cli/core/process.py` found two checks of `subprocess.run`, in `DefaultProcessRunner.run_async` and in `run_subprocess_async`. The module function was a full second copy of the runner. Without the checks, four `devops ci` tests failed with "process edge reached without a fake": they replace `subprocess.run` and reach the async start. | Done here. The module function calls the active runner, both checks go, and the four tests use `process_fake`. |
| `PYTEST_CURRENT_TEST` pass-through removed | Partly done. `rg -n PYTEST_CURRENT_TEST src/` found the allow-list entry in `core/process.py` and two reads in `commands/ci.py` (`_clean_coverage_artifacts`). #1325 is closed, but its change folder is a plan that no pull request built. The reads stop a test of the gate from deleting the `.coverage.*` files of the run that is measuring it. | The allow-list entry goes here. The two reads stay: removing them needs the `devops ci` tests to run in a root of their own, which belongs to the migration of the `ci` command tests (#3769). A ceiling of 2 in `tests/invariants/test_source_tree.py` fails on any new read. |
| Settings cache does not key on `CONFIG_PATH` | Not done. `_config_layers` keys on `str(CONFIG_PATH)`. `rg -n "CONFIG_PATH" tests` found ten rebinding sites in nine files, and one read in `test_review_untrusted_tree.py`. The floor no longer rebinds it (#1311). | Done here. The key loses the path. Every site uses a fixture. |
| Home-relative paths resolve at read time | Premise changed. `CONST_USER_DATA_ROOT` has one reader, `user_data_root()`, which reads `DEVOPS_CLI_USER_DATA_ROOT` first, and the floor sets it. The floor sets `HOME` in `tests/support/bootstrap.py` before devops-cli is imported, so `CONST_CONFIG_PATH` binds under the worker's own home (#1311). No test patches either constant. `_own_source_dir` is still patched by the floor and by three tests. `Path.home` is patched in `test_ensure_known_host`. | No change to the constants. The `_own_source_dir` patches move to the public seam `install_own_source_dir`. `test_ensure_known_host` sets `HOME`. |
| Conftest no longer assigns the GitHub token privates | Not done. `pin_github_session` assigns `process._github_token`. `tests/support/github_identity.py` assigns `_github_token` and `_lookup_github_token`. `tests/github/test_github_session.py` assigns `_github_token`. | Left for another item. The fix makes the floor answer `gh auth token` through the process runner, which is a design of its own. It touches the identity of every test. |
| Origin cache has a public reset | Partly done. `reset_repo_caches` already clears the origin cache, and the floor's reset list names it. The hand-attached `get_repo_origin_name.cache_clear` remains, with three calls in `tests/commands/test_repos.py`. | Done here. The attachment goes, and the tests call `reset_repo_caches`. |

Other facts that were checked:

- The runner has one real implementation of the async start, `DefaultProcessRunner.run_async`, and `ProcessFake.run_async` answers the same call, so the module function needs no body of its own (`rg -n "async def run_async" src tests/support`).
- `get_repo_origin_name` is called from `ci`, `gh`, `repos`, `review`, `analyze` and the refine job. All pass a root, so the reset changes no caller.
- `_source_repository` and `_repository_at` are cached by their arguments, so a changed own source directory needs no further reset than the one `reset_repo_caches` makes.

## Existing Tool Considered

- `pytest`'s `monkeypatch.setenv` covers the home and the config file, and the existing `config` and `global_config` fixtures cover the settings sites. No new tool is needed for them.
- For the own source directory, no library names "the directory that this package runs from" as a setting. The seam follows `set_process_runner`, `install_resolver` and `set_keyring_edge`: a public install function and a reset in the floor. The cost is about 15 lines in `core/repo.py`, about 2,000 tokens to write and about 500 tokens each month to keep. It deletes one private patch in the floor and three in the review tests.
