# Tasks

## 1. A line break ends the value of a credential keyword

- [x] Add failing tests: for each keyword-to-value pattern, a line that ends with the keyword or separator and a next line that starts with a credential-like word come back unchanged, with LF and CRLF line breaks, in data and code syntax; the same pair on one line is masked
  - Verification: `uv run devops ci test tests/test_consolidation_security_sanitizer.py`
- [x] Replace `\s` with `[^\S\r\n]` between each keyword or separator and its value in `_build_secret_patterns`
  - Verification: `uv run devops ci test tests/test_consolidation_security_sanitizer.py tests/test_url_credential_masking.py tests/test_review_syntax_masking.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2450-keyword-value-one-line`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
