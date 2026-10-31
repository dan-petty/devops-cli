# Proposal

## Why

Issue #1332 completes Phase E of the test harness refactoring for the `security` and `crypto` domains. Scanner, secret, and cryptographic tests previously relied on internal monkeypatching, mock-aware accommodations in production code, and direct patching of process and HTTP layers. This change migrates all remaining security and cryptographic tests to edge fakes (`scanner_fake`, `tool_executor_fake`, `process_fake`, `stub_web`, `otlp`, and `keyring_store`), removes internal patches, and cleans up residual test accommodation code.

## What Changes

- Scanner and tool tests execute over the `scanner_fake` and `tool_executor_fake` fixtures instead of patching internal scanner methods or process runners.
- HTTP calls in threat intelligence, OSV vulnerability lookups, and HashiCorp Vault interactions run through the `stub_web` fixture.
- Distributed cache lookups for Cloudflare Radar use the Valkey fake from #1317.
- Secret resolution tests use the `keyring_store` fixture and Vault HTTP stubs instead of patching `get_keyring_secret` or broker internals.
- Telemetry secret sanitization tests verify exported spans through the `otlp` fake (`FakeCollector`) rather than intercepting `trace_span`.
- Residual `# noqa: F401` unused imports in `src/devops_cli/security/ruff.py` are removed.
- `tests/test_sbom.py` validates SBOM documents using Syrupy snapshot assertions.
- `tests/test_ssh_host_keys.py` adds Hypothesis property tests for known_hosts file parsing and removes internal logger patches.
- Module-level `runner = CliRunner()` instances in security test files are replaced by the isolated `cli` fixture.
- This change alters no consumer-observed CLI behavior or commands, so it sets `skip_specs: true`.
- This change fits one pull request.

## Feasibility

- `tests/support/fakes/scanners.py` provides `ScannerFake` with pre-recorded empty runs for all security tools (Bandit, Gitleaks, Kubeconform, Semgrep, Pluto, Popeye, Trivy, Zizmor).
- `tests/web_fakes.py` and the `stub_web` fixture in `tests/conftest.py` intercept all `httpx2.Client` calls without leaving the process.
- `tests/support/fakes/keyring.py` provides `FakeKeyring` with full Secret Service emulation and lifecycle inspection.
- `tests/support/fakes/otlp.py` captures OpenTelemetry spans for secret-masking assertions via `otlp.spans()`.
- Hypothesis is already configured in the repository dependencies and test runner.

## Existing Tool Considered

- `ScannerFake` and `ToolExecutorFake` from #772 and #1982 provide scanner isolation.
- `stub_web` provides HTTP interception for public and loopback services.
- `FakeKeyring` from #1318 provides OS keyring isolation.
- Building custom test doubles instead would add significant token and maintenance cost. Reusing existing shared fakes maintains harness consistency and ensures fast execution.
