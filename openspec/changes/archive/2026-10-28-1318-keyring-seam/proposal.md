# Proposal

## Why

Issue #1318, phase D of #1307: the OS keyring and the Secret Service had no seam.

- `config/settings.py` imported `keyring` in seven functions. Backend selection, reads, writes, deletes, presence checks and the in-memory store for headless runs each reached the library on their own.
- Callers reached past it: `commands/config.py`, `commands/ai.py`, `k8s/credentials.py` and `commands/k8s/stack_lifecycle.py` imported the private `_keyring_has`, `_keyring_get`, `_keyring_set` and `_EPHEMERAL_CI_SECRETS`. `commands/config.py` asked the `keyring` library for the active backend itself. `commands/devcontainer.py` connected to the session-bus socket and asked `secretstorage` whether the default collection was locked.
- Tests patched `keyring.get_keyring`, `keyring.get_password` and the private names, and installed `FakeKeyring` from `tests/cluster_secret_fakes.py` by patching the library.

## What Changes

- `src/devops_cli/config/os_keyring.py` is the one module that reaches the keyring and the Secret Service. A `KeyringEdge` Protocol names its three questions: the backend that the `keyring` library selected, whether a D-Bus daemon answers on the session-bus socket, and whether the default Secret Service collection is locked. `SystemKeyring` is the real edge. `set_keyring_edge` and `reset_keyring_edge` install and restore it.
- Every keyring operation moves into the seam: `has_encrypted_backend` (was `_ensure_keyring_backend`), `get_keyring_secret`, `has_keyring_secret` (was `_keyring_has`), `store_keyring_secret` (was `_keyring_set`), `set_keyring_secret`, `keyring_read`, `keyring_write`, `keyring_delete`, `require_persistent_keyring`, `backend_info`, and the in-memory store with its public `remember_secret` and `clear_remembered_secrets` (was `_EPHEMERAL_CI_SECRETS` and `clear_ephemeral_ci_secrets`). `SecretStorageError`, `KeyringLockedError` and `KeyringUnavailableError` move with them. Each caller imports them from the seam. `config/settings.py` keeps no keyring code.
- `commands/devcontainer.py` asks the seam for the session-bus and lock states. `devops config audit-keys` names the backend through `backend_info`, and `devops config auth-headless` stores its token with `remember_secret`.
- `get_keyring_secret` and `has_keyring_secret` catch only the errors of a keyring that cannot answer: `keyring`'s `KeyringError`, and on Linux `secretstorage`'s `SecretStorageException`. Any other exception, a defect, now propagates instead of reading as a missing secret. `set_keyring_secret` catches `SecretStorageError`, which `store_keyring_secret` raises for every failure, so it behaves as before.
- `FakeKeyring` moves to `tests/support/fakes/keyring.py`. It is a `keyring` backend and a `KeyringEdge`: entries in memory, a locked state, a selected backend that a test can replace (for example with the library's fail backend), the session-bus and lock answers, and a record of reads, writes and bus checks. The `keyring_store` fixture installs it through the seam and replaces `mock_keyring`.
- The floor installs a deny edge through the seam before each test and resets the edge and the in-memory store after it.
- `tests/config/test_keyring_contract.py` is the fake's contract suite.
- No command, option or message changes, so the change has no spec delta (`skip_specs: true`).
- This change fits one pull request.

## Impact

- New: `src/devops_cli/config/os_keyring.py`, `tests/support/fakes/keyring.py`, `tests/config/test_keyring_contract.py`.
- Changed source: `config/settings.py`, `commands/config.py`, `commands/ai.py`, `commands/devcontainer.py`, `commands/vault.py`, `commands/k8s/cluster_secret_push.py`, `commands/k8s/stack_lifecycle.py`, `k8s/credentials.py`, `k8s/secret_push.py`, `security/secrets.py`, `security/vault_broker.py`, `github/secrets.py`, `docker/cosign.py`, `ai/rag/embeddings.py`.
- Tests: the floor (`tests/conftest.py`, `tests/invariants/test_hermetic_floor.py`), `tests/cluster_secret_fakes.py`, the tests that patched the library or the private names, and every test that requested `mock_keyring`.
- Documents: `docs/TESTING.md` and the two keyring pages of the knowledge base. `tests/fixtures/swallowed_failures_ceilings.json` lowers `config/settings.py` from 5 to 2.

## Feasibility

- The premise was measured on origin/main 6a5447a5: `config/settings.py` imported `keyring` in seven functions; the callers above imported the private names; `commands/devcontainer.py` held the socket probe and the `secretstorage` lock check; 6 test files patched `keyring` names and 9 named the private functions.
- Ordering and ownership: #1312, the item's dependency, and #1310, which added the floor's deny backend, are closed. No open item owns the keyring seam. #1322, #1323, #1325, #1332 and #1333 move their packages onto this seam's fake later. #454 is closed as not planned. No owner comment orders #1318 after another open item.
- keyring 25.7.0 (`keyring/backends/SecretService.py`): `get_preferred_collection` raises `KeyringLocked` when the collection stays locked, so a read, write or delete of a locked collection raises it; `get_password` returns `None` for a missing entry; `delete_password` raises `PasswordDeleteError("No such password!")`. `get_preferred_collection` calls `secretstorage.dbus_init()` outside its `try`, so a session bus that fails raises `secretstorage`'s `SecretServiceNotAvailableException`, not a `KeyringError`. The fake follows these answers.
- secretstorage 3.5.0: `dbus_init()` raises `SecretServiceNotAvailableException` when `DBUS_SESSION_BUS_ADDRESS` is unset, before it connects. The contract suite uses this to run the real lock check with no bus.
- `uv tree --invert --package keyring`: fastmcp reaches `keyring` through `py-key-value-aio`'s `keyring` extra. Third-party code therefore calls the library below the seam, so the floor keeps the library's deny backend as well as the deny edge.
- The owner's comment on this item (2026-10-24): a test starts no system program, so the real side of the contract suite over gnome-keyring-daemon on a private session bus is not built. The choice is recorded in the design.
- `uv run devops ci` passed on the branch.

## Existing Tool Considered

The change builds no tool. The `keyring` library's `KeyringBackend` is the base of the fake, its fail backend stands for a host with no usable keyring, and `secretstorage` stays the real lock check. The seam is a Protocol and one module over them.

The change deletes: the keyring block of `config/settings.py` (`_ensure_keyring_backend`, `_is_unencrypted_backend`, `_EPHEMERAL_CI_SECRETS`, `_keyring_get`, `_keyring_has`, `_keyring_set`, `_headless_auth_enabled`, `clear_ephemeral_ci_secrets` and the moved functions and errors); `_is_session_bus_running` and `_keyring_is_locked` in `commands/devcontainer.py`; the `mock_keyring` fixture; `FakeKeyring` in `tests/cluster_secret_fakes.py`; the tests' patches of `keyring.get_keyring`, `keyring.get_password`, `keyring.set_password` and of the private names.
