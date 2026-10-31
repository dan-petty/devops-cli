# Proposal

## Why

Issue #1327 delivers Phase E package test refactoring for the infra command test suite under parent issue #1307. The 17 identified infra command test files under `tests/commands/` currently patch internal application functions (`load_settings`, `commands.valkey._resolve_client`, `tf._resolve_tf_binary`, `cloudflare._resolve_client`, `telemetry.query_jaeger_trace`, `vault.VaultSecretBroker`, `tf.is_dry_run`, `telemetry.get_tracer`) and import private symbols. This change refactors the 17 test files to test commands through public interfaces over shared edge fakes and seams, and moves command business logic into domain packages.

## What Changes

- Move Terraform binary and directory resolution logic from `src/devops_cli/commands/tf.py` into public helpers in `src/devops_cli/tf/`.
- Move secret-leak detection logic from `src/devops_cli/commands/config.py` into public helpers in `src/devops_cli/config/` (and update `tests/test_zero_plaintext_invariants.py` to use the public import).
- Move Cloudflare Access bypass-IP resolution logic from `src/devops_cli/commands/cloudflare.py` into `src/devops_cli/cloudflare/` (or keep thin delegation as needed).
- Move Vault path validation logic from `src/devops_cli/commands/vault.py` into `src/devops_cli/security/` or `src/devops_cli/vault/`.
- Eliminate internal monkeypatches and private imports across all 17 target test files:
  - `tests/commands/test_cloudflare_commands.py`
  - `tests/commands/test_config_audit_keys.py`
  - `tests/commands/test_config_cmd.py`
  - `tests/commands/test_config_commands.py`
  - `tests/commands/test_prometheus.py`
  - `tests/commands/test_scan.py`
  - `tests/commands/test_telemetry_cmd.py`
  - `tests/commands/test_telemetry_profile.py`
  - `tests/commands/test_tf.py`
  - `tests/commands/test_tf_notify_plan.py`
  - `tests/commands/test_valkey.py`
  - `tests/commands/test_vault_cmd.py`
  - `tests/commands/test_argo.py`
  - `tests/commands/test_docker.py`
  - `tests/commands/test_grafana.py`
  - `tests/commands/test_kustomize.py`
  - `tests/commands/test_tls_cmd.py`
- Replace module-level `CliRunner()` instances with the `cli` fixture.
- Rename tests to describe behaviour without generic suffixes (`_success`, `_failure`, `_basic`, `_command`).
- This change alters no consumer-observed CLI behaviour or command syntax, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/commands/`: commands become thin adapters that delegate domain logic to underlying packages.
- `tests/commands/`: tests exercise CLI command parsing, wiring, exit codes, and output over edge fakes (`process_fake`, `keyring_store`, `http_fake`, `cli`) without monkeypatching internal functions.

## Feasibility

- `ProcessFake` (`process_fake`) intercepts subprocess execution for terraform, docker, kustomize, argocd, vault, and scanners.
- `KeyringFake` (`keyring_store`) provides in-memory secret storage for config and credential operations.
- `Respx` / `http_fake` handles HTTP requests for Prometheus, Grafana, Cloudflare, and Argo CD without network access.
- `ValkeyFake` provides in-memory Redis/Valkey command handling without a live daemon.

## Existing Tool Considered

- `ProcessFake` handles command subprocesses without invoking live binaries.
- `KeyringFake` handles OS keyring operations without OS dependencies.
- `Respx` handles HTTP client operations without live network traffic.
- Reusing existing shared test doubles eliminates 185 internal patch sites and 18 private imports across the 17 files while keeping test execution hermetic and fast.
