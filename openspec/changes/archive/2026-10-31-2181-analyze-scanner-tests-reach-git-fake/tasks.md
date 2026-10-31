# Tasks

## 1. Measure Baseline Test Duration

- [x] 1.1 Measure baseline test duration for the 13 test files <!-- id: 0 -->

## 2. Migrate Test Files to Git Fake

- [x] 2.1 Migrate `tests/commands/test_analyze.py` to `git_fake` <!-- id: 1 -->
- [x] 2.2 Migrate `tests/ai/analyze/test_ai_analyze_outlines.py` to `git_fake` <!-- id: 2 -->
- [x] 2.3 Migrate `tests/ai/test_repomap.py` to `git_fake` <!-- id: 3 -->
- [x] 2.4 Migrate `tests/ai/test_ai_diagram.py` to `git_fake` <!-- id: 4 -->
- [x] 2.5 Migrate `tests/ai/ast/test_treesitter_engine.py` to `git_fake` <!-- id: 5 -->
- [x] 2.6 Migrate `tests/security/test_security_semgrep.py` to `git_fake` <!-- id: 6 -->
- [x] 2.7 Migrate `tests/security/test_scanner_tool_executor.py` to `git_fake` <!-- id: 7 -->
- [x] 2.8 Migrate `tests/security/test_secops.py` to `git_fake` <!-- id: 8 -->
- [x] 2.9 Migrate `tests/security/test_osv_scanner.py` to `git_fake` <!-- id: 9 -->
- [x] 2.10 Migrate `tests/commands/test_security_bandit.py` to `git_fake` <!-- id: 10 -->
- [x] 2.11 Migrate `tests/security/test_scanner_contract.py` to `git_fake` <!-- id: 11 -->
- [x] 2.12 Migrate `tests/core/test_scan_complexity.py` to `git_fake` <!-- id: 12 -->
- [x] 2.13 Migrate `tests/ai/client/test_url_credential_masking.py` to `git_fake` <!-- id: 13 -->

## 3. Verify Duration and Quality Gates

- [x] 3.1 Measure test duration after migration and record comparison <!-- id: 14 -->
- [x] 3.2 Pass all quality checks (`uv run devops ci`) <!-- id: 15 -->
