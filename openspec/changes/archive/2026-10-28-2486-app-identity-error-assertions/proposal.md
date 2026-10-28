# Proposal

## Why

Issue #2486: the error-path tests and the log test in `tests/test_github_app_identity.py` do not follow docs/TESTING.md, section "Names and assertions". That section says that an assertion compares whole values, that a test of an error path checks the `DevOpsCLIError` subclass with its exit code and machine-readable error code, and that tuple equality is only for picking fields out of an object whose other fields are noise. The tests check a tuple of substring booleans on the message, and no test reads the exit code or the error code. So a change to the exit code, the error code or the rest of the message does not make them fail.

## What Changes

- `test_an_installation_without_a_requested_permission_fails_naming_the_permissions`, `test_the_key_without_the_apps_settings_fails_naming_them` and `test_a_key_that_is_no_rsa_key_fails_before_any_request` compare `DevOpsCLIError.to_dict()` of the raised error with the whole expected value: the error code, the whole message, the exit code and the details.
- `test_a_reply_that_grants_more_keeps_the_token_and_logs_only_the_permission_names` compares the token, and the records of the logger `devops_cli.github.app_installation` in `caplog.record_tuples` with the whole expected record: the logger, the level and the whole message. The whole message shows that the log holds no token and no permission level.
- `test_a_refused_exchange_raises_the_unauthenticated_error_with_githubs_status` keeps its assertion. Its whole message tells the operator to run `gh auth login` or to set GH_TOKEN, which is wrong for a process that acts as the App, and it drops GitHub's reason. #2491 fixes that message, and its test then compares the whole error. A whole-value assertion here would hold the wrong text.
- The change sets `skip_specs: true` in `.openspec.yaml`. It changes tests only. No `devops` command, option, message, manifest or service changes.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/test_github_app_identity.py`.

## Feasibility

- docs/TESTING.md, lines 93-95 at origin/main 08d70ca6, give the three rules that the tests break.
- `DevOpsCLIError.to_dict()` (`src/devops_cli/exceptions/base.py`) returns `error_code`, `message`, `exit_code` and `details`, so one comparison checks the whole error.
- pytest 9.1.1 `caplog.record_tuples` gives each record as `(logger name, level, message)`.
- Command output: with `CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE` changed to `GITHUB_OPERATION_FAILED` and a word added to the log message of `mint_installation_token`, the test file of origin/main passes (11 passed), and the changed test file fails 3 tests: the HTTP 422 test, the test of the key that is no RSA key and the log test.
- Command output: the whole message of the HTTP 401 test, read from the pytest diff, is ``GitHub App devops-roadmap[bot] has no installation token: GitHub refused the session's token for POST /app/installations/42/access_tokens (HTTP 401); log in again with `gh auth login`, or set GH_TOKEN to a valid token. Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY.`` #2491 records it.

## Existing Tool Considered

pytest's `pytest.raises` and `caplog.record_tuples`, and the project's `DevOpsCLIError.to_dict()`, cover the need. The change builds nothing. It deletes the tuples of substring booleans in the four tests.
