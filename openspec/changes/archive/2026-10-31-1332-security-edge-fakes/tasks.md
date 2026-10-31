# Tasks

## 1. Source cleanup

- [x] Remove unused `run_subprocess` import with `# noqa: F401` in `src/devops_cli/security/ruff.py`
  - Verification: `git diff src/devops_cli/security/ruff.py`

## 2. Test isolation and fakes migration

- [x] Migrate `tests/test_vulnerability_lookup.py` off `unittest.mock.patch` onto `stub_web`
  - Verification: `uv run pytest tests/test_vulnerability_lookup.py`
- [x] Migrate `tests/test_security_threat_intel.py` off HTTP patching and MagicMock onto `stub_web` and the #1317 Valkey fake
  - Verification: `uv run pytest tests/test_security_threat_intel.py`
- [x] Migrate `tests/test_vault_broker.py` off `_REQUEST` and `_FALLBACK` patches onto `stub_web` and `keyring_store`
  - Verification: `uv run pytest tests/test_vault_broker.py`
- [x] Migrate `tests/test_secret_resolution.py` off `_post` and keyring patches onto `stub_web` and `keyring_store`
  - Verification: `uv run pytest tests/test_secret_resolution.py`
- [x] Migrate `tests/test_dependency_remediator.py` off internal patches onto `stub_web` and `scanner_fake`
  - Verification: `uv run pytest tests/test_dependency_remediator.py`
- [x] Migrate `tests/test_security_semgrep.py` off internal patches onto `scanner_fake`
  - Verification: `uv run pytest tests/test_security_semgrep.py`
- [x] Migrate `tests/test_scan_outcomes_and_gating.py` off internal patches onto `scanner_fake` and `gate_report`
  - Verification: `uv run pytest tests/test_scan_outcomes_and_gating.py`
- [x] Migrate `tests/security/test_scan_report.py` off `ScannerRegistry` patches onto `scanner_fake`
  - Verification: `uv run pytest tests/security/test_scan_report.py`
- [x] Migrate `tests/security/test_sarif_emission.py` off `ScannerRegistry` patch onto `scanner_fake`
  - Verification: `uv run pytest tests/security/test_sarif_emission.py`
- [x] Migrate `tests/security/test_scanner_base_and_registry.py` off `patch.object` onto dummy failing scanner
  - Verification: `uv run pytest tests/security/test_scanner_base_and_registry.py`
- [x] Migrate `tests/test_security_sandbox_and_protection.py` off `patch("trace_span")` onto `otlp` fake
  - Verification: `uv run pytest tests/test_security_sandbox_and_protection.py`
- [x] Replace module-level `runner = CliRunner()` in `tests/test_security_zizmor.py` and `tests/test_security_bandit.py` with `cli` fixture
  - Verification: `uv run pytest tests/test_security_zizmor.py tests/test_security_bandit.py`

## 3. Snapshots and property tests

- [x] Add Syrupy snapshot assertions for SBOM documents in `tests/test_sbom.py`
  - Verification: `uv run pytest tests/test_sbom.py`
- [x] Add Hypothesis property tests for known_hosts in `tests/test_ssh_host_keys.py` and remove internal warning logger patch
  - Verification: `uv run pytest tests/test_ssh_host_keys.py`

## 4. Verification and gate

- [x] Verify zero internal patches to `devops_cli` names across security and crypto tests
  - Verification: `rg -n 'from unittest.mock import.*patch|import.*patch' tests/security/ tests/test_security_*.py tests/test_crypto_*.py tests/test_ssh*.py`
- [x] Pass all CI checks and archive change
  - Verification: `uv run devops ci`
