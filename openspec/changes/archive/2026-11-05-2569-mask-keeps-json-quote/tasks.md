# Tasks

## 1. A quote mark stays unless the value opened it

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`, `src/devops_cli/commands/gh.py` (`api_cmd`), `tests/security/test_secret_redaction.py`. Changes: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`, `tests/security/test_redaction_properties.py`, `tests/commands/test_gh_cmd.py`.

- [x] 1.1 In `tests/security/test_secret_redaction.py`, add a test for a `?<keyword>=<secret>` query parameter in a JSON string. Use `token`, `auth_token`, `password`, `client_secret` and `aws_secret_access_key`, in data and code syntax. Assert that `json.loads` parses the result.
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py` fails on the base
- [x] 1.2 In the same file, add a test for the quote marks. Cover a string in single quote marks and a value in a pair of quote marks. Cover a closing mark of the other kind. Cover a bare value at the end of the text and before a space.
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py`
- [x] 1.3 In the same file, add a test for an escaped quote mark after the secret in a JSON string. Add a test for a secret that ends in a double backslash.
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py` fails before task 1.7
- [x] 1.4 In `tests/security/test_redaction_properties.py`, add a property for nine credential keywords. Masked JSON text of a URL with a secret must still parse. Let the text after the secret hold a quote mark or a backslash.
  - Verification: `uv run devops ci test tests/security/test_redaction_properties.py` fails before task 1.7
- [x] 1.5 In `tests/commands/test_gh_cmd.py`, add a test for `devops gh api`. Fake gh at the process edge. The reply has a `token=` query parameter in `download_url`. Assert that the printed text parses as JSON.
  - Verification: `uv run devops ci test tests/commands/test_gh_cmd.py` fails on the base
- [x] 1.6 In `src/devops_cli/security/sanitizer.py`, add `_quoted(value)`. It wraps a value pattern in the group `(?P<quote>["'])?` and the closing `(?(quote)(?P=quote)?)`. Use it in the rules for `password|passwd|pwd`, `token|auth_token`, `aws_secret_access_key` and `client_secret`. Describe the pair in its docstring.
  - Verification: `uv run devops ci test tests/security tests/commands/test_gh_cmd.py tests/ai/client/test_url_credential_masking.py`
- [x] 1.7 In the same file, add the constant `_VALUE_CHAR`. It ends a value before `\"` and `\'` and keeps a double backslash whole. Use it in the rules for `password` and `token`.
  - Verification: `uv run devops ci test tests/security tests/commands/test_gh_cmd.py tests/invariants`

## 2. Archive

Kind: documentation. Reads: none. Changes: `openspec/changes/`, `openspec/specs/`.

- [x] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 2569-mask-keeps-json-quote`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
