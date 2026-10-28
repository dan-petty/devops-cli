# Tasks

## 1. Whole-value assertions in the GitHub App identity tests

- [x] 1.1 Change the tests of HTTP 422, of the missing settings and of the key that is no RSA key to compare `to_dict()` of the raised error with the whole expected value
  - Verification: `uv run devops ci test tests/test_github_app_identity.py`
- [x] 1.2 Change the log test to compare the token, and the records of the logger `devops_cli.github.app_installation` with the whole expected record
  - Verification: `uv run devops ci test tests/test_github_app_identity.py`
- [x] 1.3 Show that the changed tests fail when the error code or the log message changes, and that the tests of origin/main pass
  - Verification: change `CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE` and the log message of `mint_installation_token` in the working tree, run `uv run pytest tests/test_github_app_identity.py` with the test file of each revision, then restore the source

## 2. Static checks

- [x] 2.1 Run the ratchets and the type check
  - Verification: `uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py` and `uv run mypy src`

## 3. Archive

- [x] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 2486-app-identity-error-assertions`

## Workflow follow-up

- #2491 changes the message of a refused JWT exchange, and its test then compares the whole error of the HTTP 401 test.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
