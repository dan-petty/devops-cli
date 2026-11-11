# Design

## Decisions

- **The real home is the `HOME` that `isolate_home` replaces.** `isolate_home` keeps it in the stash of the config. The controller adds it to the `workerinput` of each xdist worker in `pytest_configure_node`, and a worker reads it from there, because the worker inherits the isolated `HOME` of the controller. A pytester run in the same process records the `HOME` that its test sets, so a test can put the real home of the inner run in its own temporary directory.
- **The guard keeps three roots writable under the real home:** the run's temporary directory, the checkout with its common git directory (`checkout_roots` of `tests/support/host_paths.py`), and the interpreter (`sys.prefix`, `sys.base_prefix`, `sys.exec_prefix`, `sys.base_exec_prefix` and `sys.pycache_prefix` when it is set). Python writes bytecode caches into the interpreter, and a GitHub-hosted runner has the checkout in its home. The workspace tripwire checks the checkout.
- **The guard refuses the same three events as the config write guard:** an open for writing, a rename onto a path and a removal. A path relative to a directory descriptor is not checked, as in the other two guards.
- **`hold_to_the_run` reads the run that the guard records at `pytest_configure`.** No run in the process means no pytest run, so the helper refuses. The refusal is `pytest.fail`, which an `except Exception` in a calling script does not hide.
- **One table of audit events.** `tests/support/file_changes.py` holds the events and the function that gets the changed path from an event. It is in `tests/`, not in `src/`: the fail-to-pass replay runs this `tests/` on the base's source, which lacks a name that the change adds to `src/`.

## Rejected alternatives

- **The home from the user database (`pwd.getpwuid(os.getuid()).pw_dir`).** It gives the same home in each worker with no transfer. But a test cannot put the real home of an inner run in its temporary directory without a patch of the user database. Also, the issue defines the real home as the `HOME` before `isolate_home`.
- **The `HOME` of each worker before `isolate_home`.** A worker inherits the isolated `HOME` of the controller (`isolate_home` sets `os.environ["HOME"]` at `pytest_configure`, and xdist starts the workers at session start). That home is in the run, so the guard would keep nothing.
- **An environment variable that carries the real home to the workers.** Each child process of a test would inherit it, and a test that clears the environment would lose it.
- **`PYTEST_VERSION` as the sign of a pytest run.** pytest sets it in `os.environ`, so a child process of a test inherits it, also when no floor runs in that child. The new test runs the helper in such a child process.
- **A refusal when `tests.support` is imported outside pytest.** `devops ci` runs `tests.support.git_recording` and `tests.support.check_test_settings` from plain Python (`src/devops_cli/commands/ci.py`, the `git` and `test-settings` rows).
- **A third copy of the audit event table in the new guard.** The config write guard and the spend ledger write guard each held a copy. One module now holds it.
