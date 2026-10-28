# Tasks

## 1. The next line does not decide the call check

- [x] 1.1 Add failing tests: an unquoted `api_key`, `access_token` or `bearer_token` value is masked when the next line, or a line after a blank line, starts with `(`, with LF and CRLF line breaks, in data and code syntax; a call with a space before `(` on the same line stays unmasked; a property shows that the line after a credential line never changes the result for that line
  - Verification: `uv run devops ci test tests/test_consolidation_security_sanitizer.py`
- [x] 1.2 Replace `(?!\s*\()` with `(?![^\S\r\n]*\()` in the `api_key` rule, and say in the comment of `_build_secret_patterns` that the call check also stops at a line break
  - Verification: `uv run devops ci test tests/test_consolidation_security_sanitizer.py tests/test_url_credential_masking.py tests/test_review_syntax_masking.py tests/test_review_defenses_and_verification.py`
- [x] 1.3 Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. A test holds each whitespace class

- [x] 2.1 Add a pair with the line break between the keyword and its separator for the `password`, `token`, `aws_secret_access_key`, `client_secret` and `api_key` rules, and a pair with the line break after `token` before a `secret_` word
  - Verification: `uv run devops ci test tests/test_consolidation_security_sanitizer.py`
- [x] 2.2 Compare the one-line result of each pair with its whole expected text, with a space, a tab or a no-break space between the two parts
  - Verification: `uv run devops ci test tests/test_consolidation_security_sanitizer.py`

## 3. Archive

- [x] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 2471-call-check-one-line`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
