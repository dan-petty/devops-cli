# Tasks

## 1. A closing quote mark stays unless a quote mark opened the value

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`, `src/devops_cli/commands/gh.py` (`api_cmd`), `tests/security/test_secret_redaction.py`. Changes: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`, `tests/security/test_redaction_properties.py`, `tests/commands/test_gh_cmd.py`.

- [ ] 1.1 In `tests/security/test_secret_redaction.py`, add a test that masks a `?<keyword>=<secret>` query parameter inside a JSON string for `token`, `auth_token`, `password`, `client_secret` and `aws_secret_access_key`, in data and code syntax, and asserts that `json.loads` parses the result. Add a second test for the quote marks: a string in single quote marks, a value in a pair of double or single quote marks, a closing mark of the other kind, and a bare value at the end of the text and before a space. In `tests/security/test_redaction_properties.py`, add a property that the masked JSON text of a URL with any of nine credential keywords still parses. In `tests/commands/test_gh_cmd.py`, add a test that `devops gh api` prints a contents reply with a `token=` query parameter as JSON that parses
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py tests/security/test_redaction_properties.py tests/commands/test_gh_cmd.py` fails on the base
- [ ] 1.2 In `src/devops_cli/security/sanitizer.py`, add `_quoted(value)`, which wraps a value pattern in the group `(?P<quote>["'])?` and the closing `(?(quote)(?P=quote)?)`. Use it in the rules for `password|passwd|pwd`, `token|auth_token`, `aws_secret_access_key` and `client_secret`, in place of their pairs of `["']?`. Describe the pair in the docstring of the helper
  - Verification: `uv run devops ci test tests/security tests/commands/test_gh_cmd.py tests/ai/client/test_url_credential_masking.py tests/invariants/test_architectural_invariants.py`

## 2. Archive

Kind: documentation. Reads: none. Changes: `openspec/changes/`, `openspec/specs/`.

- [ ] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 2569-mask-keeps-json-quote`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
