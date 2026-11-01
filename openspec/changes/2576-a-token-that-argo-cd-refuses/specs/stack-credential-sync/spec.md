## ADDED Requirements

### Requirement: Retry on 401 with stored password
When the Argo CD API returns HTTP 401 and an admin password is stored, the command SHALL mint a new token, store it in the keyring, and retry the request once.

#### Scenario: 401 with password stored
- **WHEN** the Argo CD API returns HTTP 401 and argocd.password is stored in the keyring
- **THEN** the command mints a new token via POST /api/v1/session, stores it as argocd_token, and sends the original request again

### Requirement: Error on 401 without password
When the Argo CD API returns HTTP 401 and no admin password is stored, the command SHALL stop with one error line that names argocd.token and the credential sync command.

#### Scenario: 401 without password
- **WHEN** the Argo CD API returns HTTP 401 and argocd.password is not stored
- **THEN** the command exits with one error line naming argocd.token and the credential sync command, with no traceback

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

### Requirement: Argo CD API errors are DevOpsCLIError
Every Argo CD API error SHALL be raised as a DevOpsCLIError subclass so the exit seam reports it.

#### Scenario: error type check
- **WHEN** the Argo CD API returns an error status
- **THEN** the raised exception is an instance of DevOpsCLIError
