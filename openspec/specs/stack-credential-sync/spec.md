# stack-credential-sync Specification

## Purpose
How `devops k8s sync-secrets` keeps the Argo CD admin password and the API tokens of Argo CD and Grafana in the OS keyring: it keeps a stored token that the service accepts, mints a new token only when the service refuses the stored one, and reports each failed step with its cause.

## Requirements

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

### Requirement: A failed check keeps the stored token
When the check of a stored token fails, the sync SHALL send no mint, revoke or create request to that service, SHALL leave the stored token in the keyring, and SHALL report the token as `failed` with a cause that names the URL, the status or the request error, and that the stored token stays.

#### Scenario: The Grafana check gets HTTP 502 or times out
- **WHEN** Grafana answers the check of the stored token with HTTP 502, or the check times out
- **THEN** the only request of the sync to Grafana is the check, the keyring holds the stored token, and `grafana_token` is `failed` with the cause `The Grafana token check at <url>/api/org failed with HTTP 502; the stored token stays in the keyring` or `... failed: ReadTimeout: <message>; the stored token stays in the keyring`

#### Scenario: The Argo CD check fails
- **WHEN** Argo CD answers the check with HTTP 502, the check times out, or the answer is not a JSON object
- **THEN** the sync opens no admin session, the keyring holds the stored token, and `argocd_token` is `failed` with the cause

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

### Requirement: A failed read of the Argo CD admin password reaches the sync result with its cause
The sync SHALL report `argocd` as `failed`, with a cause, when kubectl fails with an error other than NotFound, its output is not a JSON object, a field of the Secret is not base64-encoded UTF-8 text, or the keyring does not store the password. A Secret that does not exist SHALL make `argocd` `missing`.

#### Scenario: A Secret field cannot be decoded
- **WHEN** the `password` field of `argocd/argocd-initial-admin-secret` is not base64-encoded UTF-8 text
- **THEN** `argocd` is `failed` with the cause `Field password of Secret argocd/argocd-initial-admin-secret is not base64-encoded UTF-8 text`, and the sync sends no request to Argo CD

#### Scenario: kubectl cannot read the Secret
- **WHEN** kubectl fails with `Error from server (Forbidden)`
- **THEN** `argocd` is `failed` with the cause `kubectl cannot read Secret argocd/argocd-initial-admin-secret: Error from server (Forbidden): ...`

### Requirement: The command shows each failure and exits with status 1
`devops k8s sync-secrets` SHALL print one line for each credential of the result: a success line, a line that the secret was not found, or the label of the credential with its cause. When a credential is `failed`, the command SHALL exit with status 1.

#### Scenario: The Grafana check fails during the command
- **WHEN** `devops k8s sync-secrets` runs and Grafana answers the check of the stored token with HTTP 502
- **THEN** the output holds `Grafana Token: The Grafana token check at <url>/api/org failed with HTTP 502; the stored token stays in the keyring`, and the command exits with status 1

### Requirement: The Grafana commands fall back to the admin password with the cause
When no Grafana token is stored and the mint of a token fails, `get_or_mint_grafana_auth` SHALL return the basic authentication of the admin password and SHALL log a warning with the cause of the failed mint.

#### Scenario: The mint fails for a Grafana command
- **WHEN** no Grafana token is stored, the keyring holds the admin password, and Grafana refuses the create of the service account with HTTP 500
- **THEN** the requests use basic authentication with the admin password, and the warning is `The Grafana token mint failed, so the requests use the admin password: Grafana refused to create the devops-cli service account with HTTP 500`

### Requirement: A missing Grafana admin password message names the keyring entry and the commands
When the keyring holds no `grafana_password`, `devops k8s sync-secrets` SHALL print a message that names the keyring entry `grafana_password`, the command `devops config set grafana.password`, and the command `devops k8s push-secrets`. It SHALL NOT say that a Secret is missing from the cluster.

#### Scenario: The keyring has no Grafana admin password
- **WHEN** the keyring holds no `grafana_password` and the sync runs for the `infra` stack
- **THEN** the output says that the Grafana admin password is not in the keyring (`grafana_password`) and names `devops config set grafana.password` and `devops k8s push-secrets`

### Requirement: The Grafana mint creates and stores the new token before it revokes the old ones
The mint SHALL list the tokens of the `devops-cli` service account, create the new token, store it in the keyring, and only then revoke the listed tokens. A failed create or a failed store SHALL send no revoke and SHALL keep the stored token. A refused revoke SHALL NOT fail the mint: the mint SHALL keep the new token, log a warning with the cause, and leave the old token.

#### Scenario: The create fails
- **WHEN** Grafana answers the create of the token with HTTP 500
- **THEN** the sync sends no DELETE request, the keyring holds the stored token, and `grafana_token` is `failed` with the cause `Grafana refused to create a token for service account 7 with HTTP 500`

#### Scenario: The mint succeeds
- **WHEN** the account holds old token 3 and Grafana accepts every request
- **THEN** the requests and the keyring write happen in the order create, store `grafana_token`, revoke token 3

### Requirement: The token check and the mint dial at the configured level
The token check and the mint of Argo CD and Grafana SHALL dial loopback and public addresses, and private addresses only when `ai.allow_private_network` is true. This SHALL apply in `devops k8s sync-secrets` and in the commands that mint a missing token. An address that the level refuses SHALL make the check or the mint fail with a cause that names the refusal, as a request error does.

#### Scenario: A private Grafana address without the flag
- **WHEN** `ai.allow_private_network` is false, the keyring holds a Grafana token, the host of `grafana.url` answers `192.0.2.10`, and the sync runs
- **THEN** the sync reports `grafana_token` as `failed` with a cause that names the refusal, no dial occurs, and the stored token stays in the keyring

#### Scenario: A private Grafana address with the flag
- **WHEN** `ai.allow_private_network` is true, the keyring holds a Grafana token, the host of `grafana.url` answers `192.0.2.10`, and the sync runs
- **THEN** the check dials `192.0.2.10`

### Requirement: The push writes Argo CD's GitHub notifier Secret
The cluster Secret push SHALL write Secret `argocd/argocd-notifications-secret` of stack `infra`: key `github-appID` from setting `argocd.github_app_id`, key `github-installationID` from setting `argocd.github_app_installation_id`, and key `github-privateKey` from keyring entry `argocd_github_app_private_key`, each byte for byte. A change of the Secret SHALL restart no workload.

#### Scenario: A PEM key and two IDs reach the Secret
- **WHEN** namespace `argocd` exists, the keyring holds a three-line PEM-shaped value under `argocd_github_app_private_key`, and `DEVOPS_CLI_ARGOCD_GITHUB_APP_ID` and `DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID` are set
- **THEN** `devops k8s push-secrets --only argocd/argocd-notifications-secret` writes the three keys with those values byte for byte, restarts nothing, and prints no value

#### Scenario: The dry run names the keys and makes no request
- **WHEN** `devops k8s push-secrets --only argocd/argocd-notifications-secret --dry-run` runs
- **THEN** the output names each key with a placeholder of its source and no value, and no command runs

### Requirement: Each notifier key is optional and is never generated
Each key of `argocd/argocd-notifications-secret` SHALL be optional. A missing value SHALL be left out with a warning that names `devops config set <key>`, and the push SHALL generate no value for it.

#### Scenario: No value is set
- **WHEN** namespace `argocd` exists and neither setting nor the keyring entry has a value
- **THEN** the push exits 0, writes no Secret, and names `devops config set argocd.github_app_id`, `devops config set argocd.github_app_installation_id` and `devops config set argocd.github_app_private_key`

### Requirement: The Argo CD chart creates no notifications Secret
The Argo CD values SHALL set `notifications.secret.create` to false, so the push is the one owner of `argocd-notifications-secret`, and the `homelab` AppProject SHALL ignore that Secret as an orphan.

#### Scenario: The values and the project
- **WHEN** `k8s/argocd/values.yaml` and `k8s/argocd/apps/projects.yaml` are read
- **THEN** `notifications.secret.create` is false and the `homelab` project's `orphanedResources.ignore` holds Secret `argocd-notifications-secret`

### Requirement: A derived entry is built from other values of the same push
A cluster Secret table entry MAY have a derived source: a template whose fields are keyring, setting or literal sources. The push SHALL resolve every entry that is not derived first. It SHALL then fill each field with the value of its source, quoted with `urllib.parse.quote(value, safe="")`, and SHALL compare the result with the live value as for any other entry. The push SHALL NOT adopt, generate or store a derived value in the keyring.

#### Scenario: A connection string from a literal user and a generated password
- **WHEN** a row has a `password` entry from an empty keyring key with a generator, and after it in the table a derived `DSN` entry `postgres://{user}:{password}@db.example.com:5432/app` with the literal user `app/user` and the same keyring key as `password`, and no live Secret exists
- **THEN** the push writes `password` with the generated value, stores that value in the keyring, and writes `DSN` so that `urllib.parse.urlsplit` gives back the user `app/user`, the generated password, the host `db.example.com` and the path `/app`, and the keyring holds no value for `DSN`

#### Scenario: A derived entry before its input in the table
- **WHEN** the derived `DSN` entry comes before the `password` entry that adopts the live password, and the live `DSN` was built from that password
- **THEN** the plan shows `DSN` as `unchanged`

#### Scenario: A missing input
- **WHEN** an optional derived entry reads a managed keyring option that has no value
- **THEN** the push leaves the entry out, and its warning names the input and `devops config set <option>`

#### Scenario: The plan and the dry run show a derived entry with no value
- **WHEN** `--plan` or `--dry-run` runs for a row with a derived entry
- **THEN** the output names the entry's source as `derived from` and its input sources, the dry run shows a placeholder in the Secret's data and lists no keyring write for the entry, and no output holds a value

#### Scenario: A differing derived value needs rotate
- **WHEN** the live value of a derived entry differs from the value the push builds, and `--rotate` is not given
- **THEN** the push writes nothing and names the entry as differing

### Requirement: A row names its Secret type
A cluster Secret table row MAY name its Secret type, and the default SHALL be `Opaque`. The manifest that the push applies and the manifest that the dry run shows SHALL carry the type of the row.

#### Scenario: A basic-auth row
- **WHEN** the push writes a row of type `kubernetes.io/basic-auth` and a row with no type
- **THEN** the applied manifest of the first has `type: kubernetes.io/basic-auth` and the second has `type: Opaque`, and the dry run's manifest shows the same types

### Requirement: Mattermost database credential push
The cluster Secret push table SHALL declare row `mattermost/mattermost-db` under stack `chat` with secret type `kubernetes.io/basic-auth`, literal user `mattermost`, keyring password key `mattermost_db_password`, and derived connection string key `DB_CONNECTION_STRING`.

#### Scenario: Mattermost database secret attributes
- **WHEN** the cluster Secret push table is inspected
- **THEN** row `mattermost/mattermost-db` has type `kubernetes.io/basic-auth` and belongs to stack `chat`
- **AND** `DB_CONNECTION_STRING` resolves to a PostgreSQL connection URL with quoted credentials
