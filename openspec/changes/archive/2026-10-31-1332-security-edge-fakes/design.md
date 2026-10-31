# Design

## Context

Issue #1332 completes Phase E migration for `security/` and `crypto/` tests. Tests previously patched internal implementation functions such as `run_subprocess`, `_post`, `get_keyring_secret`, and `trace_span`. This change routes all tests through explicit edge seams and fakes established in Phases A through D.

## Decisions

### 1. Scanner and tool execution via `scanner_fake` and `tool_executor_fake`

- Tests in `tests/test_security_semgrep.py`, `tests/test_scan_outcomes_and_gating.py`, and `tests/security/test_scan_report.py` use `scanner_fake` to script scanner outputs.
- Direct patches to `run_semgrep_scan`, `run_trivy_scan`, and `ScannerRegistry` methods are removed.
- Tests verify real finding generation and exit codes through the scanner adapters and registry.

### 2. HTTP lookups via `stub_web`

- Vulnerability lookup tests in `tests/test_vulnerability_lookup.py` and `tests/test_dependency_remediator.py` use `stub_web` to respond to OSV API and Shodan queries.
- Cloudflare Radar threat intelligence tests in `tests/test_security_threat_intel.py` use `stub_web` and the #1317 Valkey fake.
- HashiCorp Vault tests in `tests/test_vault_broker.py` and `tests/test_secret_resolution.py` use `stub_web` to simulate Vault HTTP endpoints.

### 3. Keyring and secret resolution via `keyring_store`

- Secret tests in `tests/test_vault_broker.py` and `tests/test_secret_resolution.py` use `keyring_store.values` to seed and verify stored secrets.
- Direct patches to `get_keyring_secret` and `set_keyring_secret` are eliminated.

### 4. Telemetry and masking via `otlp` fake

- Secret-masking tests in `tests/test_security_sandbox_and_protection.py` opt into the `otlp` fixture (`FakeCollector`).
- Assertions verify that `subprocess.error_sample` attributes in exported spans have redacted tokens.

### 5. Document snapshots and property tests

- `tests/test_sbom.py` validates rendered CycloneDX and SPDX SBOM payloads against Syrupy snapshot assertions.
- `tests/test_ssh_host_keys.py` adds Hypothesis property tests to verify that `_ensure_known_host` correctly handles arbitrary whitespace, comments, host aliases, and malformed lines without crashing.

## Rejected Alternatives

- Retaining unit test mocks for external HTTP APIs: Rejected because mock patching couples tests to internal client helper structure rather than validating the HTTP boundary.
- Using real subprocesses for scanner tests in CI: Rejected because security tools are heavy external binaries that may not be present in every environment.
