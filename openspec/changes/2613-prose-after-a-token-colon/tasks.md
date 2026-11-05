# Tasks

## 1. A plain word after a credential keyword and a colon is left as written

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`. Changes: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`.

- [x] 1.1 In `tests/security/test_secret_redaction.py`, add a test that a plain word after `token:`, `auth_token:` or `password:` comes back unchanged. Cover the buildx error, a word with a leading capital and a word before a full stop. Add a second test that masks a credential after a colon. The second test also masks a plain word after `=`, `:=` or `: =`, and a plain word in quotes. Both tests run in data and code syntax
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py` fails on the base
- [x] 1.2 In `_build_secret_patterns`, name the separator of the `password|passwd|pwd` rule and of the `token|auth_token` rule as the group `sep`. In `_mask_literal`, return the match as written when `sep` is a colon and the value has no quote. The value must not start with `=`. The value must read as a word, with a full stop at its end removed. Describe the rule in the docstring of `_mask_literal`
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py tests/security/test_redaction_properties.py tests/review/test_review_syntax_masking.py tests/ai/test_review_finding_losses.py`

## 2. Archive

Kind: documentation. Reads: none. Changes: `openspec/changes/`, `openspec/specs/`.

- [x] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 2613-prose-after-a-token-colon`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
