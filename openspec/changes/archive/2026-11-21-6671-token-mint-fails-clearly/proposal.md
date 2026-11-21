# Proposal: #6671

## Why
A git child that reaches a remote gets the session's token. When the App mint failed, the process kept no token for 60 seconds, and git ran with no token. The remote then gave "Repository not found", and the log did not show the failed mint as the cause. Closes #6671.

## What Changes
- When the process acts as the GitHub App, a git child that reaches a remote raises `GitHubUnauthenticatedError` before it starts if the mint fails, as a gh call does.
- A person's git child runs with no token when the lookup finds none, and the remote gives its own error.
- A lookup that finds no token is not kept, so the next call looks again. The 60 second window and `DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS` are removed.

## Capabilities
- `subprocess-environment`: adds the requirement for a network git child when no token resolves.

## Impact
- `src/devops_cli/core/process.py`: `_session_github_token` and `_github_pin`.
- `src/devops_cli/config/defaults.py`: removes `DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS`.
- No setting, command or output changes for a person who is logged in.

## Feasibility
`_github_pin` in `src/devops_cli/core/process.py` already raises through `github_token()` for a gh child. The App path of `_lookup_session_token` calls `mint_installation_token`, which raises with the App login and the reason. The test of this change fails on main with "DID NOT RAISE GitHubUnauthenticatedError".

## Existing Tool Considered
None applies: the change removes code from the project's own process runner and adds no new mechanism.
