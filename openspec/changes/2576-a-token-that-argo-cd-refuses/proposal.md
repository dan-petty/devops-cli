# Proposal

## Why

#2576: When Argo CD rejects the stored token with HTTP 401, every Argo CD API command ends in a Python traceback. The httpx2.HTTPStatusError is not a DevOpsCLIError, so the exit seam does not report it. The token path never replaces a stored token that the server refuses. The user must delete the keyring entry by hand.

## What Changes

- Add argocd_api_request helper in src/devops_cli/argo/credentials.py that handles 401 retry with token minting and raises ArgoError on failure
- Update cd_apps_sync in src/devops_cli/commands/argo.py to use the helper instead of raw raise_for_status
- Update cd_apps_list and cd_apps_status in src/devops_cli/commands/argo.py to use the helper instead of raw raise_for_status
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stack-credential-sync`: Retry on 401 with stored password, Error on 401 without password, Error on retry 401, Error on other HTTP status, Argo CD API errors are DevOpsCLIError

## Impact

- Code: `src/devops_cli/argo/credentials.py`, `src/devops_cli/commands/argo.py`

## Feasibility

- The premise is confirmed: src/devops_cli/commands/argo.py cd_apps_sync calls resp.raise_for_status() which raises httpx2.HTTPStatusError, not a DevOpsCLIError, so the exit seam of new_typer() does not report it.
- src/devops_cli/argo/credentials.py resolve_argocd_server_and_token takes the stored argocd.token first. src/devops_cli/k8s/credentials.py get_or_mint_argocd_token mints only when no token is stored, so a rejected stored token is never replaced.
- mint_argocd_token in src/devops_cli/k8s/credentials.py already calls POST /api/v1/session and stores the token. ArgoError in src/devops_cli/exceptions/argo.py is a DevOpsCLIError subclass.
- First checks: uv run devops ci test tests/test_argo_credentials.py verifies the helper handles 401 retry, 401 without password, retry 401, and other HTTP errors. uv run devops ci test tests/test_argo_commands.py verifies the commands use the helper and raise ArgoError.

## Existing Tool Considered

mint_argocd_token in src/devops_cli/k8s/credentials.py already calls the Argo CD session API (POST /api/v1/session) and stores the token. The fix reuses this function. ArgoError in src/devops_cli/exceptions/argo.py already exists as a DevOpsCLIError subclass. Nothing new is built.
