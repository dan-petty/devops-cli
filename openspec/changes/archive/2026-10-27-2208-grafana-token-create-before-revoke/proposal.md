# Proposal

## Why

Issue #2208: `mint_grafana_token` in `src/devops_cli/k8s/credentials.py` revokes every token of the `devops-cli` service account, then creates the new token. When the create fails (network error, HTTP 5xx, refused request), the account has no token, and each caller that used a stored token loses access until a later sync succeeds.

## What Changes

- The mint lists the old tokens, creates the new token, stores it in the keyring, and only then revokes the old tokens. A failed create or a failed store sends no revoke and keeps the stored token.
- A refused revoke does not fail the mint. The mint keeps the new token, logs the cause as a warning, and leaves the old token. A later mint revokes it.
- A failed list stays a failed mint, because the list now comes before the create and changes nothing.
- The observable order of the Grafana requests and the result of a refused revoke change, so the change carries a spec delta. This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stack-credential-sync`: the order of the mint steps, and the result of a refused revoke.

## Impact

- Code: `src/devops_cli/k8s/credentials.py`.
- Tests: `tests/test_k8s_credentials.py`.

## Feasibility

- The Grafana service account token API lists tokens with `GET /api/serviceaccounts/{id}/tokens`, creates one with `POST` on the same path, and deletes one with `DELETE /api/serviceaccounts/{id}/tokens/{tokenId}`. A new token does not depend on the old ones, so the create can come first. The mint lists before the create, so the revoke cannot delete the new token.
- Source: the code of `_create_grafana_sa_token` and `_revoke_grafana_sa_tokens` before this change uses these three calls with no link between them.

## Existing Tool Considered

No open tool mints Grafana tokens in the order that this code needs. The change reorders calls of the existing code and deletes no internal code.
