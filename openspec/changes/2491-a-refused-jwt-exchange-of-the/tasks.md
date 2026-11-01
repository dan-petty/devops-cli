# Tasks

## 1. Add App-specific 401 reason to the exchange error

Reads: none. Changes: `src/devops_cli/github/app_installation.py`, `src/devops_cli/lang/git.py`.

- [ ] 1.1 Update `test_a_refused_exchange_raises_the_unauthenticated_error_with_githubs_status` in `tests/github/test_github_app_identity.py` to assert the full message: it holds `devops-roadmap[bot]`, `POST /app/installations/42/access_tokens`, `401`, `A JSON web token could not be decoded`, and `Check the App ID, the installation ID and the private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`. It does not hold `gh auth login` or `GH_TOKEN`, and verify that `uv run devops ci test tests/github/test_github_app_identity.py` fails on the base
- [ ] 1.2 In `mint_installation_token`, add an elif branch after the 422 check: if `failure.details.get("status") == HTTPStatus.UNAUTHORIZED`, replace `reason` with a new App-specific string that includes GitHub's message from `str(error)` and the request path. Add the new error string constant to `ERRORS.git` in the lang module, and verify that `uv run devops ci test tests/github/test_github_app_identity.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
