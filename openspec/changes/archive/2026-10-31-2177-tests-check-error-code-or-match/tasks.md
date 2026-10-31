# Tasks

## 1. Add AST-Grep Static Rule

- [x] Add `.ast-grep/rules/test-pytest-raises-checks-error.yml` and test `.ast-grep/rule-tests/test-pytest-raises-checks-error-test.yml`
  - Verification: `uv run ast-grep test --skip-snapshot-tests`
- [x] Register new rule in architectural invariants suites
  - Verification: `uv run pytest tests/invariants/test_architectural_invariants.py tests/commands/test_net_construct_rules.py`

## 2. Update Bare pytest.raises Sites Across Test Files

- [x] Add `match=`, `as exc_info: assert ...` or error code checks to all bare `pytest.raises` sites
  - Verification: `uv run ast-grep scan --rule .ast-grep/rules/test-pytest-raises-checks-error.yml tests` returns 0 violations

## 3. Verify Criteria and Run CI Suite

- [x] Verify scratch case triggers ast-grep failure
  - Verification: Scan scratch test file with bare `pytest.raises` and confirm failure
- [x] Verify three changed tests fail when error conditions change
  - Verification: Break expected error message/code in 3 tests and confirm failure
- [x] Run full CI quality suite
  - Verification: `uv run devops ci`
