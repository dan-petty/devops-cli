# Design

## The scan gate is data

`gate_report` returns a frozen `GateVerdict` with three facts, and `passed`. The command keeps the order of the old gate: it reports the failed scanners first and exits, then the named scanners that did not run, then exits silently when a finding is at or above the threshold. The sort of the names moves into `gate_report`, so the error lines stay the same.

Rejected: a verdict with one message string. The JSON output prints no error line, so the command, not the verdict, decides what to print.

Rejected: moving the gate of `devops scan sarif` and `devops scan injection` too. Each is one comparison with a different rule for a report without a threshold (`injection` fails on any finding), and #2543 names only the `devops scan` gate.

## The lease revoke builds its own registry

`revoke_lease` takes the broker and builds the session's registry itself, so the command no longer touches `LeaseRegistry`. It names the broker under `TYPE_CHECKING`: `vault_broker` does not import `vault_lease`, and the module does not need the broker at run time.

## Git signing prints nothing

`configure_git_signing` lives beside the key functions in `crypto/ssh_keys.py` and writes only git config. The command keeps a three-line `_configure_git_signing` that calls it and prints the message, because `crypto/` does not print.

## Tests

- A command test that registers or rotates a key changes to `tmp_path`, which is not a repository, and sets `GIT_CONFIG_GLOBAL` to a file under `tmp_path`. Without that, the test would turn on commit signing in the checkout that runs it.
- The dive symlink test needs the real `shutil.which`, which `process_fake` replaces, so it installs a `ProcessFake` through `set_process_runner` and asserts that it got no call. The old test also caught `OSError` and passed in silence; it now fails if the symlink cannot be made.
- `only_bandit` depends on `scanner_fake`, which puts every recorded scanner on `PATH`, and then sets `PATH` to one directory with only `bandit` in it.
- The user-level config of `test_review_untrusted_tree.py` is written at `CONFIG_PATH` under the worker's isolated HOME, and the fixture restores the file and removes the directories it made, so the tripwire that checks the worker home stays quiet.

Rejected: a new fake for `which`. `PATH` is the real edge, and a directory under `tmp_path` sets it.
