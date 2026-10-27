## MODIFIED Requirements

### Requirement: A token check tells acceptance, refusal and failure apart
The sync SHALL send the stored token as a bearer token to Argo CD `/api/v1/session/userinfo` or to Grafana `/api/org`. HTTP 401 or 403 SHALL count as a refusal, and so SHALL an Argo CD answer of HTTP 200 whose `loggedIn` is not `true`. Another 2xx answer SHALL count as acceptance. Any other status, an Argo CD answer that is not a JSON object, or a request error SHALL count as a failed check.

#### Scenario: Grafana refuses the stored token
- **WHEN** Grafana answers the check of the stored token with HTTP 401 or 403, and the keyring holds the Grafana admin password
- **THEN** the sync creates a token, stores it in the keyring as `grafana_token`, revokes the old tokens of the `devops-cli` service account, and reports `grafana_token` as `synced`

#### Scenario: Argo CD reports the stored token as logged out
- **WHEN** Argo CD answers the check of the stored token with HTTP 200 and `loggedIn: false`, and the cluster holds the Argo CD admin password
- **THEN** the sync opens an admin session with that password, stores its token in the keyring as `argocd_token`, and reports `argocd_token` as `synced`

#### Scenario: The service accepts the stored token
- **WHEN** Grafana answers the check with HTTP 200, or Argo CD with HTTP 200 and `loggedIn: true`
- **THEN** the sync sends no other request to that service and keeps the stored token

### Requirement: A failed token step reaches the sync result with its cause
The sync SHALL report a token as `failed`, with a cause that names the step and the status or error, when the admin session is refused or sends no token, a request of a mint fails, the service account create or search is refused, the search does not find the account, a token list or create is refused, a created token has no key, or the keyring does not store the token. A refused stored token with no admin password SHALL be `failed` too.

#### Scenario: Grafana refuses to revoke an old token
- **WHEN** Grafana answers the DELETE of old token 3 of service account 7 with HTTP 500
- **THEN** the keyring holds the new token, `grafana_token` is `synced`, and a warning says `Grafana refused to revoke token 3 of service account 7 with HTTP 500; the old token stays until a later mint revokes it`

#### Scenario: Grafana refuses to list the old tokens
- **WHEN** Grafana answers the list of the tokens of service account 7 with HTTP 403
- **THEN** the sync creates no token, and `grafana_token` is `failed` with the cause `Grafana refused to list the tokens of service account 7 with HTTP 403`

#### Scenario: The service account lookup fails
- **WHEN** Grafana answers the create of the `devops-cli` service account with HTTP 500, or answers 400 or 409 and its search does not return the account
- **THEN** the sync creates no token, and `grafana_token` is `failed` with a cause that names the refused create or the failed search

#### Scenario: Argo CD refuses the admin password
- **WHEN** Argo CD answers the admin session request with HTTP 401
- **THEN** `argocd_token` is `failed` with the cause `Argo CD refused the admin session at <url>/api/v1/session with HTTP 401`, and the keyring holds no `argocd_token`

## ADDED Requirements

### Requirement: The Grafana mint creates and stores the new token before it revokes the old ones
The mint SHALL list the tokens of the `devops-cli` service account, create the new token, store it in the keyring, and only then revoke the listed tokens. A failed create or a failed store SHALL send no revoke and SHALL keep the stored token. A refused revoke SHALL NOT fail the mint: the mint SHALL keep the new token, log a warning with the cause, and leave the old token.

#### Scenario: The create fails
- **WHEN** Grafana answers the create of the token with HTTP 500
- **THEN** the sync sends no DELETE request, the keyring holds the stored token, and `grafana_token` is `failed` with the cause `Grafana refused to create a token for service account 7 with HTTP 500`

#### Scenario: The mint succeeds
- **WHEN** the account holds old token 3 and Grafana accepts every request
- **THEN** the requests and the keyring write happen in the order create, store `grafana_token`, revoke token 3
