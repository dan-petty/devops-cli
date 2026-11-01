# argo-sync-rollouts-teardown Specification

## Purpose
Provides compliant Argo CD sync request formatting, Rollout status subresource control-plane mutations, and fail-closed cluster teardown checks.

## Requirements

### Requirement: Argo CD application sync payload structure
The system SHALL format Argo CD application synchronization request payloads with top-level `prune` and `strategy.apply.force` fields, omitting any top-level `sync` wrapper. When an application namespace is provided, the payload SHALL include `appNamespace`.

#### Scenario: App sync request with prune and force
- **WHEN** an application sync is requested with prune true and force true
- **THEN** the request payload contains `prune: true`, `strategy: {"apply": {"force": true}}`, and no `sync` key

#### Scenario: Fleet sync includes appNamespace
- **WHEN** a multi-cluster fleet synchronization is executed for an application
- **THEN** the request payload includes top-level `appNamespace` with value `argocd`

### Requirement: Rollout promote and abort status subresource targeting
Rollout promote and abort operations SHALL apply status updates directly to the Rollout status subresource. When a Rollout has `spec.paused` set to true, promotion SHALL clear `spec.paused` by setting it to false on the Rollout specification.

#### Scenario: Abort rollout patches status subresource
- **WHEN** a rollout abort is requested
- **THEN** a status patch with `{"status": {"abort": true}}` is sent to the custom object status subresource endpoint

#### Scenario: Promote rollout clears pause conditions on status subresource
- **WHEN** a rollout promotion is requested without spec.paused set
- **THEN** a status patch clearing pause conditions is sent to the custom object status subresource endpoint

#### Scenario: Promote rollout clears spec.paused when set
- **WHEN** a rollout promotion is requested for a rollout where spec.paused is true
- **THEN** the main resource is patched with `{"spec": {"paused": false}}` and the status subresource is patched to clear pause conditions

### Requirement: Rollout mutation failure handling
When a Rollout control-plane mutation is rejected by the Kubernetes API server, the mutation helper SHALL return false. When an automated rollout analysis gate abort fails, the evaluation SHALL report an `abort_failed` action.

#### Scenario: Refused abort patch yields abort_failed gate action
- **WHEN** a metric threshold fails during gate evaluation and the abort status patch is rejected by the API server
- **THEN** the rollout gate outcome action is `abort_failed`

### Requirement: Fail-closed cluster Argo CD management check
The system SHALL check whether a cluster is managed by Argo CD by reading the `cluster` Application custom resource in the `argocd` namespace via `ArgoCRDService`. An HTTP 404 response SHALL allow teardown to proceed. Any other error response or existing resource SHALL refuse teardown and display the failure reason.

#### Scenario: Teardown proceeds when Application returns 404
- **WHEN** teardown executes and the `cluster` Application custom resource returns HTTP 404
- **THEN** teardown is permitted to proceed

#### Scenario: Teardown refused when Application exists
- **WHEN** teardown executes and the `cluster` Application custom resource is found
- **THEN** teardown is refused with an error indicating Argo CD manages the cluster

#### Scenario: Teardown refused on API error
- **WHEN** teardown executes and fetching the `cluster` Application returns an API error such as HTTP 403, 500, or connection timeout
- **THEN** teardown is refused and the specific error reason is displayed

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
