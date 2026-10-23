# Task: The Valkey dashboard panel reads the flat INFO mapping and the keyring password (#1113)

**Issue**: [#1113](https://github.com/dan-petty/devops-cli/issues/1113)
**Scope**: scope/cli, scope/security
**Feasibility**: This check used valkey-py 6.2.0 and fakeredis 2.40.0 in the project environment. It also used the code of the release tip. `ValkeyClient.info()` returns the mapping that valkey-py parses from the INFO text. The parser drops the `# Server` and `# Memory` headings. The mapping is therefore flat.

A loopback listener answered INFO with a Valkey 8 text. The mapping then held `valkey_version` and `uptime_in_seconds` at the top level. `FakeValkey().info()` raises `unknown command 'info'`. The in-memory server cannot supply this shape. The tests therefore use a loopback listener.

`build_default_resolver` reads the keyring first and the plaintext `valkey.password` setting last. `get_valkey_password` therefore returns the keyring value when both exist. The new tests ran on the tree before the fix. The panel showed the version `unknown` and an uptime of 0. It sent no `AUTH` for a keyring-only password. It sent the plaintext password when both passwords existed.

## Description

Step E of #1113. The Valkey panel of the dashboard had two defects.

- `fetch_valkey_status` read `info["server"]`, `info["clients"]`, `info["memory"]` and `info["stats"]`. `ValkeyClient.info()` returns one flat mapping, as `devops valkey stats` and `tests/test_valkey.py` already read it. The panel therefore always showed the version `unknown` and an uptime of 0. It also showed the default values for memory, clients, commands and hit ratio.
- The panel passed the plaintext setting `valkey.password` to the client. It did not call `get_valkey_password`. A password in the keyring never reached the server.

The panel now reads each field from the flat mapping. It passes the password that `get_valkey_password` resolves.

The tests change with the code:

- `tests/test_ui_dashboard.py` no longer builds a nested INFO dictionary on a `MagicMock`. The new tests call `fetch_valkey_status` through a real `ValkeyClient`. The client talks to a loopback listener that answers INFO with a Valkey 8 text. The parser of valkey-py makes the mapping, so its shape cannot drift from the real client.
- The loopback listener moves from `tests/test_valkey.py` to `tests/support/fakes/valkey.py`, as `serving_valkey` with `bulk_reply`. Both test modules use it. The module docstring names it as the way to test INFO, because the in-memory server answers no INFO.
- `tests/test_ui_dashboard.py` uses the `mock_keyring` fixture for the whole module. The panel now reads the keyring. The test floor refuses a keyring that no test fakes.
- The offline test `test_fetch_valkey_status_failure` stays as it was.

The change builds no new code. It deletes the nested reads and calls the existing `get_valkey_password`.

## Acceptance Criteria

- [x] `fetch_valkey_status` reads a flat INFO reply (`test_fetch_valkey_status_reads_the_flat_info_the_client_returns`). The panel returns `version == "8.0.0"`, `uptime_seconds == 3600`, `used_memory == "2.40M"`, `connected_clients == 4`, `total_commands == 5000`, `hit_ratio == 80.0` and `key_count == 150`.
- [x] The first command that the panel sends is `AUTH` with the keyring password (`test_fetch_valkey_status_authenticates_with_the_keyring_password`). This holds when the keyring is the only source. It also holds when the plaintext `valkey.password` setting holds another value.
- [x] Each of the seven INFO fields and the password source has a mutation proof. A change to the key of one field fails a test of the panel. A return to `cfg.password` also fails a test of the panel.
- [x] `tests/test_ui_dashboard.py` builds no nested INFO dictionary.
- [x] `serving_valkey` and `bulk_reply` live in `tests/support/fakes/valkey.py`. `tests/test_valkey.py` and `tests/test_ui_dashboard.py` import them from there.
- [x] These commands pass: `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy src` and `uv run devops docs check`. The targeted tests of the changed modules pass.
- Pending a person: against a real Valkey 8, run `uv run devops dashboard --summary`. The Valkey Caching panel shows the version of the server, not `unknown`.
- Pending a person: set `requirepass` on that server and keep the password in the keyring. The same command then shows `Connected`. With a wrong keyring password, it shows `Offline`.

## Deliverables

- [x] Change `fetch_valkey_status` in `src/devops_cli/ui/data_providers.py`. It reads the flat INFO mapping and calls `get_valkey_password`.
- [x] Replace the nested-INFO test in `tests/test_ui_dashboard.py` with two tests over a real `ValkeyClient` and a loopback listener. Fake the keyring for the module.
- [x] Move the loopback listener to `tests/support/fakes/valkey.py`. Update `tests/test_valkey.py` and the module docstring.
- [x] Tick the dashboard step in `docs/agent/tasks/task-1113-valkey-py-replaces-the-hand-written-client.md`.
- Not done: the validated `valkey.url`, the vetted dial and the k8s URL writers (Steps B to D, later Parts of #1113).
- Not done: the shared fail-soft client (Step F, a later Part of #1113).
- Not done: the closing changelog (Step G, the last Part of #1113).
