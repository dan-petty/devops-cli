## Problem Description

When Argo CD rejects the stored API token, every `devops argo cd apps` command that calls the Argo CD API ends in a Python traceback, and devops-cli never gets a new token.

- `cd_apps_sync` (`src/devops_cli/commands/argo.py`) calls `resp.raise_for_status()`, so a 401 raises `httpx2.HTTPStatusError`. It is not a `DevOpsCLIError`, so the exit seam of `new_typer()` (#2502) does not report it, and the user sees a full traceback.
- `resolve_argocd_server_and_token` (`src/devops_cli/argo/credentials.py`) takes the stored `argocd.token` first. `get_or_mint_argocd_token` (`src/devops_cli/k8s/credentials.py`) mints a token with `argocd.password` only when no token is stored. A stored token that the server rejects is never replaced. Argo CD session tokens expire, so after that every Argo CD API command fails until a person deletes the keyring entry `argocd_token` by hand.

## Reproduction Steps

1. Store an expired or revoked Argo CD token as `argocd.token` (keyring `argocd_token`), with `argocd.password` also stored.
2. Run `uv run devops argo cd apps sync <application>`.

## Expected vs Actual Behavior

- Expected: on a 401, the command mints a new token with the stored admin password, stores it, and sends the request again one time. When no password is stored, or the new token is also refused, it stops with one error line that names `argocd.token` and the command that sets it. Any other HTTP error status is one error line with the status, with no traceback.
- Actual (2026-10-29, origin/main `cabfcd43`):

```
HTTPStatusError: Client error '401 Unauthorized' for url
'https://argocd.<domain>/api/v1/applications/prometheus-operator-crds/sync'
```

after a traceback through `core/cli.py:197`, `core/cli.py:98` and `commands/argo.py:295`.

## Environment Diagnostics

- `devops config show`: `argocd.token` set, `argocd.password` set, `argocd.url` set.
- The same Application synced through `kubectl -n argocd patch application <name> --type merge -p '{"operation":{"sync":{...}}}'`, so the server and the Application were healthy; only the token was refused.

## Logs, Traces, or Terminal Output

The traceback above. `devops argo cd apps retire-helm-records`, which reads through `kubectl` and not the Argo CD API, worked in the same session.

## Existing Tool Considered

Argo CD's own session API (`POST /api/v1/session`) mints the token, and `mint_argocd_token` already calls it. The fix reuses it and maps HTTP errors to the existing Argo CD error class. Nothing new is built.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=07fb4c222b09ef6bb9e6fc9cd1d5fbb45f6c9a78 -->
## Proposed design

### Problem statement
When Argo CD rejects the stored token with HTTP 401, each Argo CD API command ends in a Python traceback. The `httpx2.HTTPStatusError` is not a `DevOpsCLIError`, so the exit seam does not report it. The token path never replaces a stored token that the server refuses. The user must delete the keyring entry by hand.

### Acceptance criteria

### Requirement: Retry on 401 with stored password
When the Argo CD API returns HTTP 401 and an admin password is stored, the command SHALL mint a new token, store it in the keyring, and retry the request once.

#### Scenario: 401 with password stored
- **WHEN** the Argo CD API returns HTTP 401 and `argocd.password` is stored in the keyring
- **THEN** the command mints a new token via `POST /api/v1/session`, stores it as `argocd_token`, and sends the original request again

### Requirement: Error on 401 without password
When the Argo CD API returns HTTP 401 and no admin password is stored, the command SHALL stop with one error line that names `argocd.token` and the credential sync command.

#### Scenario: 401 without password
- **WHEN** the Argo CD API returns HTTP 401 and `argocd.password` is not stored
- **THEN** the command exits with one error line naming `argocd.token` and the credential sync command, with no traceback

### Requirement: Error on retry 401
When the retried request after minting a new token also returns HTTP 401, the command SHALL stop with one error line.

#### Scenario: retry also returns 401
- **WHEN** the command mints a new token and retries, and the Argo CD API returns HTTP 401 again
- **THEN** the command exits with one error line, with no traceback

### Requirement: Error on other HTTP status
When the Argo CD API returns any HTTP status other than 401, the command SHALL stop with one error line containing the status code.

#### Scenario: HTTP 500 response
- **WHEN** the Argo CD API returns HTTP 500
- **THEN** the command exits with one error line containing the text '500', with no traceback

### Requirement: Error is DevOpsCLIError
Every Argo CD API error SHALL be raised as a `DevOpsCLIError` subclass so the exit seam reports it.

#### Scenario: error type check
- **WHEN** the Argo CD API returns an error status
- **THEN** the raised exception is an instance of `DevOpsCLIError`

### Existing Tool Considered
No alternatives check has run. Argo CD's own session API (`POST /api/v1/session`) mints the token, and `mint_argocd_token` in `src/devops_cli/k8s/credentials.py` already calls it. The fix reuses this function and maps HTTP errors to the existing `ArgoError` class. Nothing new is built.

### Key questions
- **How should the 401 retry work across the Argo CD API commands?**: A shared helper in `src/devops_cli/argo/credentials.py` wraps the Argo CD API call. On HTTP 401, it mints a new token via `mint_argocd_token`, stores it, and retries the request once. The commands in `src/devops_cli/commands/argo.py` call this helper instead of a raw `client.post` plus `resp.raise_for_status`. (best practice) [sources: src/devops_cli/argo/credentials.py, src/devops_cli/k8s/credentials.py, src/devops_cli/commands/argo.py]
  - Chosen: Shared helper in argo/credentials.py. One place for the retry logic, beside the existing token functions. Avoids duplicating the retry across four or more commands.
  - Rejected: Per-command try/except in commands/argo.py. Duplicates the mint-and-retry logic in every command that calls the Argo CD API.
  - Rejected: Pre-verify the token in resolve_argocd_server_and_token. Adds an extra HTTP call to every command. The body specifies a reactive retry on 401, not a proactive check.
- **Which exception should the Argo CD API commands raise on HTTP errors?**: Raise `ArgoError` from `src/devops_cli/exceptions/argo.py`. It is a `DevOpsCLIError` subclass, so the exit seam of `new_typer()` reports it as one error line with no traceback. (best practice) [sources: src/devops_cli/exceptions/argo.py, src/devops_cli/commands/argo.py]
  - Chosen: ArgoError. Existing Argo CD error class. It is a DevOpsCLIError subclass, so the exit seam reports it with its message and exit code.
  - Rejected: typer.Exit(1). Bypasses the exit seam. The user sees no structured error message.
  - Rejected: A new exception class. Unnecessary. ArgoError already exists and is imported by the Argo commands.
- **What should the error message say when no password is stored and the token is refused?**: The error line names `argocd.token` and the credential sync command that sets it, so the user knows what to fix. (best practice) [sources: src/devops_cli/k8s/credentials.py]
  - Chosen: Name the key and the sync command. Tells the user exactly which keyring entry to fix and which command to run.
  - Rejected: A generic authentication-failed message. Does not tell the user how to fix the problem.
- **Where should the retry helper function live?**: In `src/devops_cli/argo/credentials.py`, beside the existing `resolve_argocd_server_and_token` function. (best practice) [sources: src/devops_cli/argo/credentials.py]
  - Chosen: argo/credentials.py. Already holds Argo CD credential and token resolution logic. The helper belongs with the code it calls.
  - Rejected: commands/argo.py. Mixes command logic with credential logic. The commands should call the helper, not define it.
  - Rejected: A new module. Unnecessary for one function. Adds a file with no other content.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->
