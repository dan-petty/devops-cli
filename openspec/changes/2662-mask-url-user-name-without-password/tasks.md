# Tasks

## 1. The user name of a URL with no password is masked

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`. Changes: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`, `tests/security/test_redaction_properties.py`, `tests/ai/client/test_url_credential_masking.py`, `tests/k8s/test_gitea_doctor.py`.

- [x] 1.1 In `tests/security/test_secret_redaction.py`, add a test that `redact_text` masks the user name of a URL with no password, in data and code syntax. Cover a token, a harmless name, JSON text, a URL inside a query, a user and a password, an `@` after the authority and an empty user name. Change the `user-only` case of the `mask_uri_credentials` test to the new rule. In `tests/security/test_redaction_properties.py`, add a property for any scheme and host. In `tests/ai/client/test_url_credential_masking.py`, change the cases that held the old behavior and add an IPv6 case. In `tests/k8s/test_gitea_doctor.py`, change the expected message of the `ssh://git@` case to show `<masked-user>`
  - Verification: `uv run devops ci test tests/security/test_secret_redaction.py tests/security/test_redaction_properties.py tests/ai/client/test_url_credential_masking.py` fails on the base
- [x] 1.2 In `_mask_url_candidate`, mask a user name with no password as `<masked-user>`. In `mask_uri_credentials`, mask a user name with no password as `***`. Use the parser results that the functions read today, and add no pattern
  - Verification: `uv run devops ci test tests/security tests/ai/client/test_url_credential_masking.py tests/invariants/test_architectural_invariants.py`
- [x] 1.3 State the rule in the module docstring of `sanitizer.py`, and point to it from the docstrings of `redact_text` and `mask_uri_credentials`
  - Verification: `git grep -n "masked-user" src/devops_cli/security/sanitizer.py`

## 2. Archive

Kind: documentation. Reads: none. Changes: `openspec/changes/`, `openspec/specs/`.

- [ ] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 2662-mask-url-user-name-without-password`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
