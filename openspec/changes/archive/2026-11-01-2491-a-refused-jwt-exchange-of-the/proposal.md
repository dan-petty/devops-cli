# Proposal

## Why

Issue #2491: when GitHub refuses the App's JWT with HTTP 401, the error message tells the operator to run `gh auth login` or set `GH_TOKEN`. A process that acts as the App has no gh login, so the advice is wrong. The message also drops GitHub's reason, for example "A JSON web token could not be decoded". The spec requirement "A failed exchange names the App and the reason" asks for the reason.

## What Changes

- In `mint_installation_token` (`src/devops_cli/github/app_installation.py`), add an `elif` branch after the 422 branch. For HTTP 401 it replaces the reason with a new App-specific text that names the request, the status and GitHub's message. The text holds no advice about gh, because `_token_failed` already adds the advice to check the App ID, the installation ID and the private key to every reason.
- Add the constant `github_app_jwt_refused` to `GitErrorMessages` in `src/devops_cli/lang/en/errors.py` (reachable as `ERRORS.git`). GitHub's message is cut to `CONST_MAX_ERROR_DETAIL_LENGTH`, as the classifier does.
- Change the 401 test in `tests/github/test_github_app_identity.py` to compare the whole error with `to_dict()`, as the 422 tests of the same file do.
- Change the classifier `_unauthenticated_error` in `src/devops_cli/github/error_classifier.py` in no way. A gh session needs its text, and `tests/github/test_github_contract.py` pins it.
- Spec delta: the change alters a message that a consumer of `mint_installation_token` observes, so it carries a MODIFIED delta of `github-app-identity`.
- The change needs no document change: no document or command help names this message.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-app-identity`: A failed exchange names the App and the reason

## Impact

- Code: `src/devops_cli/github/app_installation.py`, `src/devops_cli/lang/en/errors.py`
- Tests: `tests/github/test_github_app_identity.py`
- Spec: `openspec/specs/github-app-identity/spec.md`, through the delta

## Acceptance

- GitHub's reason is in the 401 error: group 1.
- The 401 error holds no `gh auth login` and no `GH_TOKEN`: group 1.
- The 401 error tells the operator to check the App ID, the installation ID and the private key in `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`: group 1. The existing `_token_failed` wrapper writes this sentence. The new whole-message assertion pins it, and it must show once.
- The 401 error names the bot login and `POST /app/installations/42/access_tokens`: group 1.

## Feasibility

All checks ran on `origin/main` at 1c20865a on 2026-11-01.

- Mechanism. `git show origin/main:src/devops_cli/github/app_installation.py` shows `classify_http_error(error, method="POST", path=_token_path(app))` at line 115 and the 422 override at line 117 (`failure.details.get("status") == HTTPStatus.UNPROCESSABLE_ENTITY`). `grep -n "_status_is(HTTPStatus.UNAUTHORIZED)" src/devops_cli/github/error_classifier.py` prints line 243, and `_unauthenticated_error` at line 193 writes "log in again with `gh auth login`, or set GH_TOKEN to a valid token". It does not use `str(error)`, so GitHub's reason is lost.
- Reproduction. I replaced the assertion of `test_a_refused_exchange_raises_the_unauthenticated_error_with_githubs_status` with `assert raised.value.message == ""` and ran `uv run devops ci test tests/github/test_github_app_identity.py`. Result: `1 failed, 22 passed`. The diff showed: "GitHub App devops-roadmap[bot] has no installation token: GitHub refused the session's token for POST /app/installations/42/access_tokens (HTTP 401); log in again with `gh auth login`, or set GH_TOKEN to a valid token. Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY." This is the message of the issue. I reverted the change.
- Current test. `grep -n "def test_a_refused_exchange" tests/github/test_github_app_identity.py` prints line 332. Its assertion is `(BOT_LOGIN in raised.value.message, "401" in raised.value.message) == (True, True)`, so it holds no wrong text and checks no reason.
- Where `ERRORS.git` lives. `ls src/devops_cli/lang` shows `__init__.py` and `en/`, and `git ls-files src/devops_cli/lang/git.py` prints nothing. `grep -n "github_app_token_failed" src/devops_cli/lang/en/errors.py` prints line 51, in the `GitErrorMessages` dataclass. The new constant goes there.
- GitHub's reason. gidgethub's `HTTPException` gets the `message` of the response body as its text, so `str(error)` is "A JSON web token could not be decoded". The classifier already uses `str(error)[:CONST_MAX_ERROR_DETAIL_LENGTH]` in `_refused_error` and `_refused_identity_error`. `CONST_MAX_ERROR_DETAIL_LENGTH` is 256 in `src/devops_cli/config/constants.py`.
- No double advice. `github_app_token_failed` is "GitHub App {login} has no installation token: {reason}. Check the App ID, the installation ID and the private key in {key_env}." So the new reason must not repeat that sentence.
- Nothing newer. `git log origin/main --oneline -8 -- src/devops_cli/github/app_installation.py src/devops_cli/github/error_classifier.py tests/github/test_github_app_identity.py` shows no commit that handles the 401 reason. A search for open and closed issues with "401" and "JWT" in the title found no duplicate. No other change folder under `openspec/changes/` touches `github-app-identity`.

## Existing Tool Considered

No external tool or library covers this need. gidgethub already gives the status and GitHub's message, and the code reuses them. The fix is a small code change in existing code: one constant, one `elif` branch and one test change. The written cost is about 10 lines of code and 15 lines of test change, plus one run of the test file. No internal code is deleted.
