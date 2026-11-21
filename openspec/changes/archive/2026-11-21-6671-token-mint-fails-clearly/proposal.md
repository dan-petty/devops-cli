# Proposal: #6671

## Why
A git child that reaches a remote gets the session's token. When the App mint failed, the process kept no token for 60 seconds, and git ran with no token. The remote then gave "Repository not found", and the log did not show the failed mint as the cause. Closes #6671.

## What Changes
- When the process acts as the GitHub App, a git child that reaches a remote raises the error of a failed mint before it starts, as a gh call does.
- A refusal (HTTP 401, a suspended account, a key that cannot sign) stays `GitHubUnauthenticatedError`, and the Service halts. A mint that GitHub does not answer (5xx or no connection) raises `GitHubUnreadError`: the round fails, and the next round mints again. This also stops the halt that such a mint caused for a gh call.
- When a renewal fails, the kept installation token serves until it expires.
- A person's git child runs with no token when the lookup finds none, and the remote gives its own error.
- A lookup that finds no token is not kept, so the next call looks again. The 60 second window and `DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS` are removed.

## Capabilities
- `subprocess-environment`: adds the requirement for a network git child when no token resolves.
- `github-app-identity`: adds the requirement for a mint that GitHub does not answer.

## Impact
- `src/devops_cli/core/process.py`: `_session_github_token` and `_github_pin`.
- `src/devops_cli/config/defaults.py`: removes `DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS`.
- `src/devops_cli/github/app_installation.py`: `mint_installation_token` raises `GitHubUnreadError` when GitHub does not answer.
- `src/devops_cli/commands/research.py`: goes on with no token after that error too.
- No setting, command or output changes for a person who is logged in.

## Feasibility
`_github_pin` in `src/devops_cli/core/process.py` already raises through `github_token()` for a gh child. The App path of `_lookup_session_token` calls `mint_installation_token`, which raises with the App login and the reason. The test of this change fails on main with "DID NOT RAISE GitHubUnauthenticatedError".

## Existing Tool Considered
None applies: the change removes code from the project's own process runner and adds no new mechanism.
