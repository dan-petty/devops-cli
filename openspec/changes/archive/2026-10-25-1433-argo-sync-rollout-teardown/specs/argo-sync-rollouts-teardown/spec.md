# Spec Delta

## Purpose

Provides compliant Argo CD sync request formatting, Rollout status subresource control-plane mutations, and fail-closed cluster teardown checks.

## ADDED Requirements

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
