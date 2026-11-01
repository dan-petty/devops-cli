# Design

## Decisions

- **Override the 401 reason in `mint_installation_token`, as the 422 case does**: the function already replaces the 422 reason with App-specific text. A 401 branch keeps the App logic in the App module. The generic `_unauthenticated_error` stays right for gh sessions, where `gh auth login` is the correct advice.
- **Build the reason from a new constant `ERRORS.git.github_app_jwt_refused`**: "GitHub refused the App's JWT for {request} (HTTP 401): {reason}". `{request}` is `POST` and `_token_path(app)`. `{reason}` is `str(error)` cut to `CONST_MAX_ERROR_DETAIL_LENGTH`, as `_refused_error` cuts it.
- **Put no "check the App ID" advice in the new constant**: `_token_failed` adds it to every reason through `github_app_token_failed`. A second copy would show the sentence twice. The whole-message test pins that it shows once.
- **Keep `str(error)` for GitHub's reason**: gidgethub sets it to the `message` of the response body.

## Rejected alternatives

- **Change `_unauthenticated_error` to drop gh-login advice**: the classifier also serves gh sessions, where the advice is right, and `tests/github/test_github_contract.py` pins the text. See `src/devops_cli/github/error_classifier.py` line 193 and the table entry at line 243.
- **Add a classifier entry for the App 401**: the classifier does not know the App context. The 422 case is also handled in `mint_installation_token`, not in the classifier.
- **Append GitHub's reason to the current text**: the current text still tells the operator to run `gh auth login`, which is wrong for an App.
