# Proposal

## Why

Issue #2491: when GitHub refuses the App's JWT with HTTP 401, the error message tells the operator to run `gh auth login` or set `GH_TOKEN`. A process acting as the App has no gh login, so the advice is wrong. The message also drops GitHub's reason, for example "A JSON web token could not be decoded".

## What Changes

- Add a 401 elif branch in `mint_installation_token` that replaces the generic reason with an App-specific string including GitHub's message from the response body
- Add a new error string constant in `ERRORS.git` for the App 401 reason
- Update the 401 test assertion to compare the full message, confirming it holds GitHub's reason and App-specific advice, and does not hold gh-login text
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-app-identity`: A failed exchange names the App and the reason

## Impact

- Code: `src/devops_cli/github/app_installation.py`, `src/devops_cli/lang/git.py`

## Feasibility

- The premise is confirmed: `mint_installation_token` in `src/devops_cli/github/app_installation.py` line 115 calls `classify_http_error` and uses `failure.message` for 401, which comes from `_unauthenticated_error` in `src/devops_cli/github/error_classifier.py` line 193 that writes gh-login advice.
- The 422 override at line 116-117 of `app_installation.py` shows the pattern to follow: check `failure.details.get("status")` and replace `reason`.
- The test at `tests/github/test_github_app_identity.py:332` currently uses a substring assertion and will not hold the wrong text after the fix.
- The path of the `ERRORS.git` module is not shown in the inputs; the import `from devops_cli.lang import ERRORS` in `app_installation.py` confirms the package, but the defining file must be located during implementation.
- First checks: run `uv run devops ci test tests/github/test_github_app_identity.py` to confirm the existing test passes, then apply the new assertion and confirm it fails before the fix.

## Existing Tool Considered

No external tool or library covers this need. The fix is a small code change in existing code: one new error string constant, one elif branch in `mint_installation_token`, and one test assertion update. The written cost is about 15 lines of code and 10 lines of test change, plus the time to run the test suite once.
