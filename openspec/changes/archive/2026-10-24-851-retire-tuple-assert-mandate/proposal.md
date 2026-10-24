# Proposal

## Why

Issue #851 explains that historical in-house complexity rules forced developers to write tuple-equality assertions. Ruff C901 does not count assertions toward McCabe complexity. Tests also contain presence-only assertions and bare truthiness assertions that certify objects exist without asserting values.

## What Changes

- Define `CONST_PRESENCE_CHECK_NAMES` in `src/devops_cli/config/constants.py` containing `callable`, `hasattr`, and `isinstance`.
- Add an AST invariant check `_opaque_or_presence_assertions` in `tests/test_architectural_invariants.py`.
- Run the check in `test_no_test_certifies_a_failure_without_checking_it` beside the blind-raise assertion scan.
- Select Ruff lint rule `PT018` in `pyproject.toml` and add `PT018` to `CONST_TEST_ASSERTION_LINT_RULES`.
- Rewrite existing test sites across `tests/` that contain opaque tuple asserts, presence-only assertions, or bare truthiness.
- Rewrite re-export tests to assert identity with the defining object with the `is` keyword.
- This change alters test suites and lint rules only. Consumers observe no command, option, or behavior changes. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/config/constants.py`: defines `CONST_PRESENCE_CHECK_NAMES` and adds `PT018` to `CONST_TEST_ASSERTION_LINT_RULES`.
- `pyproject.toml`: selects `PT018` in `[tool.ruff.lint]`.
- `tests/test_architectural_invariants.py`: adds `_opaque_or_presence_assertions` check and fixture verification test.
- `tests/`: rewrites existing test assertions to compare values or assert identity.

## Feasibility

- Inspected `pyproject.toml` line 119 and verified that Ruff supports rule `PT018`.
- Ran `uv run ruff check --select PT018` across `tests/` to verify 38 composite assertions.
- Verified with an AST parse of `tests/` that 37 files hold opaque tuple assertions and 38 files hold presence-only test functions.
- Verified that `_opaque_or_presence_assertions` executes in under 100 ms on `parsed_test_trees`.

## Existing Tool Considered

Ruff rule `PT018` (`pytest-composite-assertion`) breaks compound boolean assertions into separate assertions. This change selects `PT018` in Ruff lint configuration. No open tool checks Python AST for custom tuple-equality patterns or presence-only test functions. Building the custom AST check in `tests/test_architectural_invariants.py` costs zero dependencies and executes within the existing test tree parse.

Deleted or rewritten internal code:
- 49 opaque tuple assertion statements across `tests/`.
- 53 presence-only test functions across `tests/`.
- 38 compound assertions flagged by `PT018`.
