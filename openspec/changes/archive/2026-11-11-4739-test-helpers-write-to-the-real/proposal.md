# Proposal: #4739

## Why

Issue #4739: a helper of `tests/support/` wrote into the real home of a developer. An agent called `link_at_pin` from plain Python, outside pytest. No conftest ran, so the floor did not isolate `HOME` or the user data root. The helper got each path from devops-cli, which put it under `~/.local/share/devops-cli/tools/`, and wrote the stub `#!/bin/sh\necho mytool\n` over 18 real tools. The helper has no guard. Inside pytest, the two write guards of the floor refuse only config files and spend ledgers, and the host path guard sees only `open()`. No guard refuses another write under the real home.

## What Changes

- The new floor module `tests/support/home_write_guard.py` adds a PEP 578 audit hook, in the form of the config write guard. While a test runs, in its setup, call and teardown, it fails the test when the test opens a file for writing, renames a file onto one or removes one under the real home and outside the run's temporary directory, the checkout and the interpreter. The failure names the test, and the test also fails at teardown when the code under test catches the failure. `_run_with_floor` in `tests/invariants/test_hermetic_floor.py` gives each inner pytester run a real home of its own.
- `isolate_home` in `tests/support/bootstrap.py` records the real home, the `HOME` that it replaces. An xdist worker inherits the isolated `HOME` of the controller, so the controller gives its real home to each worker through `workerinput`.
- `hold_to_the_run` in the new module refuses a path outside the temporary directory of the pytest run in this process. When no pytest run is active in the process, it refuses each path. `link_at_pin` calls it for each path before it writes, and the write function of the `global_config` fixture calls it before it writes the global config file.
- The new module `tests/support/file_changes.py` holds the audit events that change a file. The config write guard, the spend ledger write guard and the home write guard read them from this one module.
- `docs/TESTING.md` names the home write guard and the rule for a support helper.
- The change alters no behavior a consumer observes. It changes only the test floor, its tests and a document. So it has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: a test that writes under the real home fails at the write and names itself. A support helper that is called from plain Python stops before it writes and tells why.
- Files: `tests/support/home_write_guard.py` (new), `tests/support/file_changes.py` (new), `tests/support/bootstrap.py`, `tests/support/tools.py`, `tests/support/config.py`, `tests/support/config_write_guard.py`, `tests/support/spend_write_guard.py`, `tests/invariants/test_hermetic_floor.py`, `docs/TESTING.md`.
- No path under `src/` changes.

## Feasibility

- The cause is in the code at `origin/main` (`4b289804`). `link_at_pin` (`tests/support/tools.py`) gets each path from `installed_commands`, which puts it under `tool_dir`, which is `user_data_root() / "tools" / <name> / <version>` (`src/devops_cli/tools_lock/__init__.py`). With no `DEVOPS_CLI_USER_DATA_ROOT`, `user_data_root()` returns `CONST_USER_DATA_ROOT`, which is `Path.home() / ".local" / "share" / "devops-cli"` (`src/devops_cli/core/repo.py`, `src/devops_cli/config/constants.py`).
- The census of the support helpers that write to a path that devops-cli resolves: `git grep -nE "user_data_root\(|Path\.home\(|expanduser\(|installed_commands\(|CONST_CONFIG_PATH\.(write|parent\.mkdir)" -- tests/support` prints 3 lines in 2 members: `link_at_pin` in `tests/support/tools.py`, a plain function, and the write function of the `global_config` fixture in `tests/support/config.py`. Both call `hold_to_the_run`.
- The floor has no guard for these writes. `config_write_guard.py` and `spend_write_guard.py` refuse a write only when the file name is a config file or a spend ledger. The host path guard in `tests/conftest.py` replaces `builtins.open` and `io.open` only, so `os.open`, `os.replace` and `os.remove` pass it, and its failure in another thread fails no test.
- pytest 9.1.1 and pytest-xdist 3.8.0 are in the lock. `isolate_home` sets `os.environ["HOME"]` at `pytest_configure`, and xdist starts its workers later, at session start, so a worker inherits the isolated `HOME`. In `xdist/workermanage.py`, `WorkerController.setup` builds `workerinput` (line 308), calls `pytest_configure_node` (line 342) and then sends `workerinput` to the worker (line 349). So a hook of the controller can add the real home to `workerinput`.
- The uv interpreter of the devcontainer is under the real home: `sys.base_prefix` is `/home/vscode/.local/share/uv/python/cpython-3.14.10-linux-x86_64-gnu`. Python writes its bytecode cache there. On a GitHub-hosted runner, the checkout is under `/home/runner/work/`, in the home of the runner. So the guard keeps the checkout and the interpreter writable.
- The reproduction of the issue was not run by hand: a support helper is called only through pytest. The new test runs the same call in a child process whose `HOME` is in the test's temporary directory.

## Existing Tool Considered

- PEP 578 audit hooks (`sys.addaudithook`, in the standard library since Python 3.8) report each `open`, `os.rename` and `os.remove` with its path. The config write guard and the spend ledger write guard use them. The home write guard uses them too.
- pytest's `Stash` keeps the real home on the config of the run, and the `pytest_configure_node` hook of pytest-xdist with `workerinput` carries it to each worker.
- pyfakefs replaces the file system of a test with a fake. It does not refuse a real write, it would change every test of the suite, and it does not run outside pytest. No maintained pytest plugin fails a test on a write by its path.
- The code to build is small: about 120,000 tokens to build, about 5,000 tokens a year to keep and fix, and about 2 hours of elapsed time.
- The change deletes the two copies of the audit event table and of `_changed_path` in `tests/support/config_write_guard.py` and `tests/support/spend_write_guard.py`.
