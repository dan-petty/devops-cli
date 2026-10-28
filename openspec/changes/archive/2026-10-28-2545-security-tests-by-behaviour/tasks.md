# Tasks

## 1. The security tests split by behaviour

- [x] Split `tests/test_security_sarif.py` into seven files and `tests/test_reference_extractor.py` into six files under `tests/security/`, and dissolve the catch-all tests of the named files; compare the collected test IDs before and after
  - Verification: `uv run devops ci test tests/security tests/test_aibom.py tests/test_ssh.py tests/test_crypto_tls.py tests/test_dependency_remediator.py`
- [x] Merge the two tflint files into `tests/security/test_tflint.py`, and rename the consolidation-named files after their behaviour
  - Verification: `uv run devops ci test tests/security/test_tflint.py tests/security/test_scanner_base_and_registry.py tests/security/test_secret_redaction.py`

## 2. Snapshots, properties, builders and the cli fixture

- [x] Snapshot the SARIF document and the AIBOM document with syrupy, after checking the SARIF snapshot against `tests/golden/sarif_report.json`; delete the golden file
  - Verification: `uv run devops ci test tests/security/test_sarif_emission.py tests/test_aibom.py`
- [x] Add the redaction, suppression-policy and known_hosts properties, and break each behaviour in the code once to see its property fail
  - Verification: `uv run devops ci test tests/security/test_redaction_properties.py tests/security/test_suppression_properties.py tests/git/test_known_hosts_properties.py`
- [x] Add `make_normalized_finding`, replace the local finding factories with the builders, and replace the module-level `CliRunner()`s with the `cli` fixture
  - Verification: `uv run devops ci test tests/security tests/test_security_gitleaks.py tests/test_security_semgrep.py tests/test_scan_outcomes_and_gating.py tests/test_scan_complexity.py tests/test_sbom.py tests/test_dependency_remediator.py tests/test_vault_broker.py tests/test_ssh.py tests/test_ssh_host_keys.py`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2545-security-tests-by-behaviour`

## Workflow follow-up

- The remaining process, clock, settings and GitHub patches of these files move onto the merged fakes in #2543, and the HTTP, Valkey, secret and span tests in #2544.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
