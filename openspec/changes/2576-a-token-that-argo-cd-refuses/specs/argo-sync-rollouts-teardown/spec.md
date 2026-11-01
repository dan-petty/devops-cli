## ADDED Requirements

### Requirement: A refused Argo CD token is replaced one time
When Argo CD answers an API request of `devops argo cd apps list`, `devops argo cd apps sync` or `devops argo cd apps status` with HTTP 401, and the keyring holds `argocd.password`, the command SHALL open an admin session with `POST /api/v1/session`, store the new token in the keyring as `argocd_token`, and send the request again one time with the new token.

#### Scenario: Sync with a refused token and a stored password
- **WHEN** the keyring holds `argocd_token` and `argocd_password`, Argo CD answers the sync request that carries the stored token with HTTP 401, and answers the session request with a new token and the sync request that carries the new token with HTTP 200
- **THEN** the command sends the session request, the keyring holds the new token as `argocd_token`, the command sends the sync request again with the new token, prints that the sync is triggered, and exits with status 0

#### Scenario: Status and list with a refused token and a stored password
- **WHEN** the same refusal happens to the read of `devops argo cd apps status <name>` or `devops argo cd apps list`
- **THEN** the command replaces the token as above and shows the application in its panel or table

### Requirement: A refusal with no stored password ends the command with one message
When Argo CD answers an API request of `devops argo cd apps` with HTTP 401 and the keyring holds no `argocd.password`, `sync` SHALL print one error line that holds `401`, `argocd.token` and `devops k8s sync-secrets`, exit with status 1, print no traceback and send no session request. `status` SHALL show the same text as the error of its panel and exit with status 1. `list` SHALL show it as the error row of its table.

#### Scenario: Sync with a refusal and no stored password
- **WHEN** Argo CD answers the sync request with HTTP 401 and the keyring holds no `argocd_password`
- **THEN** the command exits with status 1, prints one error line that holds `401`, `argocd.token` and `devops k8s sync-secrets`, prints no traceback, and sends no session request

#### Scenario: Status with a refusal and no stored password
- **WHEN** Argo CD answers the status read with HTTP 401 and the keyring holds no `argocd_password`
- **THEN** the command exits with status 1 and the panel shows an error that holds `401` and `argocd.token`

### Requirement: A refusal of the new token ends the command with one message
When the request that carries the new token gets HTTP 401, or Argo CD refuses the admin session, `devops argo cd apps sync` SHALL print one error line, exit with status 1 and print no traceback. The line SHALL hold `401` in the first case, and the cause of the session error in the second. `status` and `list` SHALL show the same text as the error of their panel and table.

#### Scenario: The new token is also refused
- **WHEN** Argo CD answers HTTP 401 to the sync request that carries the stored token and to the one that carries the new token
- **THEN** the command sends the sync request two times and the session request one time, exits with status 1, prints one error line that holds `401`, and prints no traceback

#### Scenario: Argo CD refuses the admin session
- **WHEN** Argo CD answers the sync request with HTTP 401 and the session request with HTTP 401
- **THEN** the command exits with status 1 and prints one error line that holds `refused the admin session`

### Requirement: Another HTTP error status ends the command with its status
When Argo CD answers an API request of `devops argo cd apps sync` with an HTTP status that is neither 2xx nor 401, the command SHALL print one error line that holds the status, exit with status 1, print no traceback, and send no session request.

#### Scenario: HTTP 500
- **WHEN** Argo CD answers the sync request with HTTP 500
- **THEN** the command exits with status 1, prints one error line that holds `HTTP 500`, and prints no traceback

#### Scenario: HTTP 403 is not a refused token
- **WHEN** Argo CD answers the sync request with HTTP 403 and the keyring holds `argocd_password`
- **THEN** the command sends no session request, exits with status 1, and prints one error line that holds `HTTP 403`
