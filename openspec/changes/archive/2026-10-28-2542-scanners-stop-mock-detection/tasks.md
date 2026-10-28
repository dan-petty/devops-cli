# Tasks

## 1. The scanners stop looking for mocks

- [x] Move the 64 dependent patch sites onto `scanner_fake`, PATH and `set_dry_run`, and add `fail` and `answer_with` to `ToolExecutorFake` and `ScannerFake`
  - Verification: `uv run pytest tests/test_consolidation_security_scanner_base.py tests/test_security_bandit.py tests/test_security_gitleaks.py tests/test_security_semgrep.py tests/test_tflint.py tests/test_secops.py tests/test_scan_outcomes_and_gating.py tests/test_security_sarif.py tests/test_golangci_lint_scanner.py tests/test_security_zizmor.py tests/test_review_untrusted_tree.py tests/test_review_static_analyzers.py`
- [x] Delete `NonCallableMock`, `_is_mocked`, `_patched_run_subprocess` and the mock-aware branches in `security/base.py`, and the `# noqa: F401` re-imports in the seven scanner modules
  - Verification: `uv run devops ci test`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2542-scanners-stop-mock-detection`

## Workflow follow-up

- #2543: the other process, clock, settings and GitHub SSH-key patches of #1332's files, and the scan gate, the Vault lease registry and git signing out of `commands/`.
- #2544: the HTTP, Valkey, secret and span tests, after #1314, #1317, #1318 and #1319.
- #2545: the test files by behaviour, snapshots and property tests.
- #1336: bans the accommodations at zero.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
