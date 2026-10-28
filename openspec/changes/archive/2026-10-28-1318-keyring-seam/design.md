# Design

## Context

#1307 phase D gives each process edge one seam in `src`: a Protocol, the one place that supplies the real implementation, a fake under `tests/support/fakes/` and the fake's contract suite. This change does it for the OS keyring and the Secret Service behind it.

## Decisions

### The seam is a module in `config/`, with an edge Protocol

`config/os_keyring.py` holds every keyring operation as a module function, as `config/settings.py` held them, and asks one `KeyringEdge` for the system's answers: `backend()`, `session_bus_running(socket_path)` and `default_collection_locked()`. `set_keyring_edge` and `reset_keyring_edge` install and restore the edge, in the shape of the process runner's `set_process_runner` and `reset_process_runner`.

- Rejected: a class with `install` and `reset_instance` class methods, as `KubernetesService` has (#2527). `KubernetesService` was already a class that callers hold; the keyring operations were module functions that callers import, and a module-level hook keeps each call site as it is.
- Rejected: `security/` for the module. The item requires that no module in `config/` other than the seam imports `keyring`, and the settings write secrets through it.

### The functions move; `config/settings.py` keeps no delegates

The item proposed that the settings functions delegate to the seam. A function that only forwards to another is a shim, and AGENTS.md allows none. The functions move into the seam with their names, so each caller changes one import, and the private names become public operations of the seam.

### The floor denies at two levels

The floor installs a deny edge through the seam before each test, so every devops-cli reach of the keyring and of D-Bus fails, also when the code under test catches it. It keeps the deny backend that the `keyring` library takes before the first test, because fastmcp reaches the library through `py-key-value-aio`'s `keyring` extra, below the seam (`uv tree --invert --package keyring`).

- Rejected: only the deny edge. Third-party code would then reach the developer's real keyring.

### The real side of the contract suite runs only what needs no program

The contract suite runs the Secret Service checks over the fake and over `SystemKeyring`: the session-bus check against a socket that the test binds, and against a path where nothing listens (the floor refuses that connect under `@pytest.mark.unreachable`), and the lock check with no session-bus address, which `secretstorage` refuses before it connects. The entry cases run over the fake, whose answers follow keyring 25.7.0's Secret Service backend.

- Rejected: gnome-keyring-daemon on a private session bus under `dbus-run-session`, which the item first proposed. The owner's rule of 2026-10-24 (comment on #1318) is that a test starts no system program and runs the same in the devcontainer and on a stock GitHub runner. No opt-in mechanism outside the default run exists: `@pytest.mark.live` only allows named programs in the default run.

### The lenient reads catch only a keyring that cannot answer

`get_keyring_secret` and `has_keyring_secret` caught `Exception`. They now catch `KeyringError` and, on Linux, `secretstorage`'s `SecretStorageException`, which keyring's Secret Service backend passes through when the session bus fails. `set_keyring_secret` catches `SecretStorageError`.

- Rejected: moving the three blind `except Exception` sites to the new module with their ceiling. The swallowed-failures ratchet refuses a ceiling for a file that had none ("Resolve or handle the failures properly; do not raise the ceiling").
- Rejected: logging the exception with `exc_info=True` so that the lint rule accepts the blind `except`. It hides the same defects and prints a traceback with a warning.

### The fake's selected backend replaces `keyring.get_keyring` patches

A test that checks backend selection sets `keyring_store.selected` to a stand-in, such as a plaintext-named backend or a chainer, or to the library's fail backend for a host with no usable keyring. The edge returns a backend, as `keyring.get_keyring()` does, so the earlier test case of no backend object at all goes: the library never returns `None`.

### Scope left to the package items

Tests that patch a devops-cli name at its import site, such as `devops_cli.docker.cosign.get_keyring_secret` or `devops_cli.commands.vault.keyring_write`, keep those patches. They resolve the same names, now imported from the seam, and their package items move them onto `keyring_store`.
