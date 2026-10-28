# Tasks

## 1. One keyring seam with a shared fake and its contract suite

- [x] Add the contract suite `tests/config/test_keyring_contract.py` and the fake `tests/support/fakes/keyring.py` with its `keyring_store` fixture; the suite cannot run on the base, where the seam does not exist
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Add `src/devops_cli/config/os_keyring.py`, move the keyring operations, the in-memory store and the three errors into it from `config/settings.py`, move the session-bus and lock checks into it from `commands/devcontainer.py`, and point every caller at it
  - Verification: `uv run devops ci test tests/config/test_keyring_contract.py tests/test_devcontainer.py tests/test_config_cmd.py`
- [x] Install the deny edge through the seam in the floor, register the seam's resets, and delete `mock_keyring` and `FakeKeyring` in `tests/cluster_secret_fakes.py`
  - Verification: `uv run devops ci test tests/invariants/test_hermetic_floor.py`
- [x] Move the tests that patched `keyring` names or the private names onto `keyring_store` and the seam's public operations, and request `keyring_store` where `mock_keyring` was requested
  - Verification: `uv run devops ci test`
- [x] Narrow the lenient reads to the errors of a keyring that cannot answer, and lower the swallowed-failures ceiling of `config/settings.py`
  - Verification: `uv run devops ci test tests/test_swallowed_failures_ratchet.py`
- [x] Describe the deny edge and the keyring fake in `docs/TESTING.md`, point the keyring pages of the knowledge base at the seam, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1318-keyring-seam`

## Workflow follow-up

- The tests that patch a devops-cli keyring name at its import site (`tests/test_docker_cosign.py`, `tests/test_github_secrets.py`, `tests/test_vault_broker.py`, `tests/test_vault_cmd.py`, `tests/test_secret_resolution.py`) move onto `keyring_store` with their package items: #1321, #1327 and #1332.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
