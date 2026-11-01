# Design

## Decisions

- **Override the 401 reason in `mint_installation_token`, following the existing 422 pattern**: The function already overrides the 422 reason with App-specific text. Adding a 401 override follows the same pattern and keeps App logic in the App module. The generic `_unauthenticated_error` is correct for gh sessions where `gh auth login` is the right advice.
- **Include GitHub's reason from the response body in the 401 message**: The spec requirement says the error SHALL name the reason. The issue confirms that "the reason" means GitHub's actual message from the response, not a generic instruction. The 422 case already includes GitHub's text.

## Rejected alternatives

- **Change `_unauthenticated_error` to drop gh-login advice**: This function is also used for gh sessions where `gh auth login` is the correct advice. Changing it would break the gh-session case. See `src/devops_cli/github/error_classifier.py:193` and its use in `_HTTP_CLASSES` at line 243.
- **Add a new classifier entry for App 401**: The classifier is generic and does not know about the App context. Adding App-specific logic there mixes concerns. The 422 case is handled in `mint_installation_token`, not in the classifier.
