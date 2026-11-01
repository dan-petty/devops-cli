### Problem Description

When GitHub refuses the JWT of the GitHub App with HTTP 401 at `POST /app/installations/<id>/access_tokens`, the error tells the operator to log in with gh. A process that acts as the App has no gh login, so this advice is wrong. The error also drops GitHub's reason, for example "A JSON web token could not be decoded".

The cause: `mint_installation_token` in `src/devops_cli/github/app_installation.py` puts the message of `classify_http_error` into the App's error. For HTTP 401, `_unauthenticated_error` in `src/devops_cli/github/error_classifier.py` writes the text for a gh login session: "GitHub refused the session's token for <request> (HTTP 401); log in again with `gh auth login`, or set GH_TOKEN to a valid token".

The spec `openspec/specs/github-app-identity/spec.md`, requirement "A failed exchange names the App and the reason", asks for the reason. Before #2482 the code had the same behavior, so #2482 did not cause it.

### Reproduction Steps

1. In `tests/test_github_app_identity.py`, the test `test_a_refused_exchange_raises_the_unauthenticated_error_with_githubs_status` routes the exchange to HTTP 401 with the body `{"message": "A JSON web token could not be decoded"}`.
2. Replace its assertion with `assert raised.value.message == ""` and run `uv run devops ci test tests/test_github_app_identity.py`.
3. The diff shows the message.

### Expected vs Actual Behavior

Expected: the message names the bot login, the request, HTTP 401 and GitHub's reason, and tells the operator to check the App ID, the installation ID and the private key. It does not tell the operator to run `gh auth login` or to set GH_TOKEN.

Actual: `GitHub App devops-roadmap[bot] has no installation token: GitHub refused the session's token for POST /app/installations/42/access_tokens (HTTP 401); log in again with `gh auth login`, or set GH_TOKEN to a valid token. Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY.`

### Environment Diagnostics

Found at origin/main 08d70ca6 when the error-path tests of `tests/test_github_app_identity.py` changed to compare the whole message (#2486). The test of the 401 path keeps its substring assertion until this item changes the message, so that no test holds the wrong text.

### Logs, Traces, or Terminal Output

See the actual message above.

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.


Source: https://github.com/dan-petty/devops-cli/issues/2486

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
When GitHub refuses the App's JWT with HTTP 401, the error message tells the operator to run gh auth login or set GH_TOKEN. A process acting as the App has no gh login, so the advice is wrong. The message also drops GitHub's reason, such as "A JSON web token could not be decoded". The fix changes the 401 reason in mint_installation_token to include GitHub's message and App-specific advice, following the existing 422 pattern.

### Acceptance criteria

### Requirement: 401 error includes GitHub's reason
The 401 error message SHALL include the reason that GitHub gave in its response body.

#### Scenario: GitHub returns 401 with a message
- **WHEN** GitHub answers the exchange with HTTP 401 and body {"message": "A JSON web token could not be decoded"}
- **THEN** the raised GitHubUnauthenticatedError message contains "A JSON web token could not be decoded"

### Requirement: 401 error omits gh-login advice
The 401 error message SHALL NOT contain the text "gh auth login" or "GH_TOKEN".

#### Scenario: GitHub returns 401 with a message
- **WHEN** GitHub answers the exchange with HTTP 401 and body {"message": "A JSON web token could not be decoded"}
- **THEN** the raised GitHubUnauthenticatedError message does not contain "gh auth login" and does not contain "GH_TOKEN"

### Requirement: 401 error names App-specific fix
The 401 error message SHALL tell the operator to check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY.

#### Scenario: GitHub returns 401 with a message
- **WHEN** GitHub answers the exchange with HTTP 401 and body {"message": "A JSON web token could not be decoded"}
- **THEN** the raised GitHubUnauthenticatedError message contains "Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY"

### Requirement: 401 error names bot login and request
The 401 error message SHALL name the App's bot login and the request path POST /app/installations//access_tokens.

#### Scenario: GitHub returns 401 with a message
- **WHEN** GitHub answers the exchange with HTTP 401 and body {"message": "A JSON web token could not be decoded"}
- **THEN** the raised GitHubUnauthenticatedError message contains "devops-roadmap[bot]" and "POST /app/installations/42/access_tokens"

### Existing Tool Considered
No external tool or library covers this need. The fix is a small code change in existing code: one new error string constant in ERRORS.git, one elif branch in mint_installation_token (src/devops_cli/github/app_installation.py), and one test assertion update in tests/test_github_app_identity.py. The written cost is about 15 lines of code and 10 lines of test change, plus the time to run the test suite once.

### Key questions
- **Where does the fix go: in the generic classifier or in mint_installation_token?**: In mint_installation_token, following the existing 422 pattern. The generic _unauthenticated_error is correct for gh sessions where gh auth login is the right advice. The App's exchange is a special case that already overrides the 422 reason in the same function. (best practice) [sources: src/devops_cli/github/app_installation.py:111, src/devops_cli/github/error_classifier.py:192]
  - Rejected: Change _unauthenticated_error to drop gh-login advice. Rejected. This function is also used for gh sessions where gh auth login is the correct advice. Changing it would break the gh-session case.
  - Rejected: Add a new classifier entry for App 401. Rejected. The classifier is generic and does not know about the App context. Adding App-specific logic there mixes concerns.
  - Rejected: Override the 401 reason in mint_installation_token, like the existing 422 override. Chosen. The function already overrides the 422 reason with App-specific text. Adding a 401 override follows the same pattern and keeps App logic in the App module.
- **What is the exact shape of the 401 error message?**: The message follows the _token_failed wrapper: "GitHub App  has no installation token: . Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY." The reason is: "GitHub refused the JWT for POST /app/installations//access_tokens (HTTP 401): ". This matches the 422 pattern where the reason includes GitHub's text followed by App-specific advice. (best practice) [sources: src/devops_cli/github/app_installation.py:126, openspec/specs/github-app-identity/spec.md, tests/test_github_app_identity.py:222]
  - Rejected: Keep the current _unauthenticated_error text and append GitHub's reason. Rejected. The current text says "log in again with gh auth login, or set GH_TOKEN to a valid token", which is wrong for an App process.
  - Rejected: Replace the reason with App-specific text that includes GitHub's message. Chosen. The 422 case already does this: it replaces the generic reason with App-specific text. The 401 case should do the same, including GitHub's reason from the response body.
- **How does the 422 override work, as the pattern to follow?**: mint_installation_token checks failure.details.get("status") == HTTPStatus.UNPROCESSABLE_ENTITY and, if true, replaces the reason with ERRORS.git.github_app_permissions_not_granted formatted with the original reason and the asked permissions. The 401 override follows the same shape: check for HTTPStatus.UNAUTHORIZED and replace the reason with a new App-specific string that includes GitHub's message from str(error). [sources: src/devops_cli/github/app_installation.py:112, src/devops_cli/github/app_installation.py:113]
- **Does the spec require the 401 message to include GitHub's reason?**: Yes. The spec requirement "A failed exchange names the App and the reason" states: "A refused exchange, or a key that cannot sign a JWT, SHALL raise GitHubUnauthenticatedError that names the App's bot login and the reason." The scenario says the message holds the bot login and 401. The issue body clarifies that "the reason" means GitHub's actual reason from the response, not a generic gh-login instruction. [sources: openspec/specs/github-app-identity/spec.md]
- **Does the test currently hold the wrong text?**: No. The test test_a_refused_exchange_raises_the_unauthenticated_error_with_githubs_status uses a substring assertion: it checks that BOT_LOGIN and "401" are in the message. It does not assert the full message, so it will not hold the wrong gh-login text. The issue body confirms: "The test of the 401 path keeps its substring assertion until this item changes the message, so that no test holds the wrong text." [sources: tests/test_github_app_identity.py:259, openspec/changes/archive/2026-10-28-2486-app-identity-error-assertions/proposal.md]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "implement.branch": "fix/2491-a-refused-jwt-exchange-of-the", "implement.job": "devops-cli-runner-20261101-110641-6f38", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.spend": "{\"requests\": 33, \"input_tokens\": 958133, \"output_tokens\": 6187}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "4e9f3fce44006b5957e08e4df5858ed86a6b668e3cc36643c4edf837ab5bc60b", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "e2adf22810dac97c182510577704728c2c3dedc35c8223bbf70b5e373fcef167", "stage.branch": "fix/2491-a-refused-jwt-exchange-of-the", "stage.file_cap": null, "stage.groups": "[[\"Add App-specific 401 reason to the exchange error\", 5709]]", "stage.needs_split": null, "stage.pr": "2992", "stage.ready": "2992", "stage.sha": "71707298899b66867023ba04bf8505df04fa5e14"} -->
