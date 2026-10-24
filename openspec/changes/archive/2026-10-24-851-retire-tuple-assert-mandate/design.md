# Design

## Context

Historically, an in-house counter added complexity points for each `assert` statement. That counter forced tests to fold multiple checks into tuple comparisons. The migration to Ruff C901 stopped counting asserts and `with` blocks. Consequently, tuple-equality assertions are no longer necessary for complexity budgets.

Additionally, tests that perform only presence checks (`is not None`, `isinstance`, `hasattr`, `callable`) or bare truthiness checks (`assert x`) do not verify values or behavior. Re-export tests should check object identity with `is`. Other tests should compare concrete values.

## Architectural Changes

1. **Presence Check Names**: Define `CONST_PRESENCE_CHECK_NAMES = frozenset({"callable", "hasattr", "isinstance"})` in `src/devops_cli/config/constants.py`.
2. **AST Invariant Check**: Author `_opaque_or_presence_assertions` in `tests/test_architectural_invariants.py`. The function iterates through test modules and checks for:
   - Tuple-equality assertions that compare presence calls with boolean literals.
   - Test functions whose every assertion is a presence check or bare truthiness check.
   - The check ignores tests that delegate to same-module asserting helpers or perform no assertions ("does not raise" tests).
3. **Integration with Existing Invariants**: Call `_opaque_or_presence_assertions` inside `test_no_test_certifies_a_failure_without_checking_it`. It shares the session fixture `parsed_test_trees` with `_blind_exception_assertions`.
4. **PT018 Selection**: Enable Ruff rule `PT018` in `pyproject.toml` and include it in `CONST_TEST_ASSERTION_LINT_RULES`.
5. **Site Rewrites**: Update all test sites in `tests/` to eliminate opaque tuple assertions and presence-only checks.

## Rejected Alternatives

### 1. Allowlist for Presence-Only Tests
- **Alternative**: Create a lookup table or waiver list of allowed presence-only tests.
- **Rejection Evidence**: The issue establishes an explicit constraint: "Constraint: No allowlist." Tests must check values or identities.

### 2. Flagging Tests With Zero Assertions
- **Alternative**: Flag any test function that does not contain an `ast.Assert` node.
- **Rejection Evidence**: Tests that verify a call does not raise an exception do not need explicit assertions. Forcing `assert f() is None` adds no defect detection. Tests that delegate to same-module assertion helpers (such as `tests/test_security_sarif.py`) would falsely fail.

### 3. Rejecting PT018
- **Alternative**: Leave `PT018` unselected in Ruff lint configuration.
- **Rejection Evidence**: Leaving `PT018` unselected allows compound assertions (`assert a and b`). When a compound assertion fails, pytest does not report which clause failed. Selecting `PT018` enforces assertion decomposition across the test suite.
