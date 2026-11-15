# Proposal

## Why

The masker replaced a lower-case name after the word `Secret` or `token` with `<masked-token>`, so `devops roadmap intake` refused a candidate whose body named Secret `devops-cli` or the subcommand `token revoke-self` (#5240).

## What Changes

- Add `_has_a_token_shape` to `src/devops_cli/security/sanitizer.py`: a value after a space-separated keyword masks only with a digit, a dot, an internal capital, or a length of 24 or more. A lower-case hyphenated name stays.
- Keep the wider rule of `_mask_literal` for the assignment forms (`token:`, `token=`, a quoted value, `--token <value>`), and keep `_looks_like_a_credential` for them.
- Add the two negative cases in `tests/security/test_secret_redaction.py`, built from parts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `secret-masking`: a lower-case name after a keyword is not a credential.

## Impact

- Code: `src/devops_cli/security/sanitizer.py`
- Tests: `tests/security/test_secret_redaction.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/security/sanitizer.py:342` holds the space-separated rule, and `:73:def _mask_credential_like_value(` gates it.
- `:202:def _mask_literal(` holds the assignment forms.
- `uv run pytest tests/security/test_secret_redaction.py` passes after the change with 289 cases.

## Existing Tool Considered

The masker holds its rule table and tests. The change narrows one rule: about 1,000 tokens to build and 100 a quarter to keep.

## Dependencies

None.
