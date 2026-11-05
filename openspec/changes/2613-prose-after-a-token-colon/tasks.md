# Tasks

## 1. A plain word after a credential keyword and a colon is left as written

Reads: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`. Changes: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`.

- [x] 1.1 In `tests/security/test_secret_redaction.py`, add two tests in data and code syntax: a plain word after `token:`, `auth_token:` or `password:` comes back unchanged (the buildx error, a word with a leading capital, a word before a full stop), and a credential after a colon, a plain word after an equals sign and a plain word in quotes are masked
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py` fails on the base, and the failing cases are the prose cases
- [x] 1.2 In `_build_secret_patterns`, name the separator of the `password|passwd|pwd` rule and of the `token|auth_token` rule as the group `sep`. In `_mask_literal`, return the match as written when `sep` is a colon, the value has no quote, and `_looks_like_a_credential` of the value without a full stop at its end is false. Describe the rule in the docstring of `_mask_literal`
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py tests/security/test_redaction_properties.py tests/review/test_review_syntax_masking.py tests/ai/test_review_finding_losses.py`

## 2. Archive

- [ ] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 2613-prose-after-a-token-colon`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
