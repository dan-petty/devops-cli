# argo-workflow-logs Specification

## Purpose
Provides native Kubernetes pod name resolution and container selection for streaming logs from Argo Workflows executions.

## Requirements

### Requirement: Deterministic Argo Workflows pod name resolution
The Argo custom resource engine SHALL derive Kubernetes pod names matching Argo Workflows pod naming conventions for both `v1` (node ID) and `v2` (`<workflow>-<templateName>-<hash>`) naming versions. Nodes that were not created, including skipped or omitted execution nodes, SHALL be excluded.

#### Scenario: Pod names derived under v2 naming
- **WHEN** resolving pod names for a workflow with multiple steps under default v2 naming
- **THEN** pod names match the format `<workflow>-<templateName>-<hash>` computed from the FNV-32a hash of the node name

#### Scenario: Single-step workflow entrypoint pod under v2 naming
- **WHEN** resolving pod names for a single container template workflow whose node name equals the workflow name
- **THEN** the pod name matches the workflow name directly without template or hash suffix

#### Scenario: Pod names derived under v1 naming
- **WHEN** resolving pod names for a workflow annotated with `workflows.argoproj.io/pod-name-format: v1`
- **THEN** pod names equal the node identifiers in the workflow status

#### Scenario: Skipped and omitted nodes are excluded
- **WHEN** a workflow contains nodes with phase `Skipped` or `Omitted`
- **THEN** those nodes are omitted from the resolved pod list

### Requirement: Container selection for Argo Workflows log streaming
The `devops argo workflows logs` command SHALL target the `main` container by default and accept a `--container` (`-c`) option to target an alternate container.

#### Scenario: Default container is main
- **WHEN** streaming logs without specifying a `--container` option
- **THEN** the Kubernetes log streaming service is invoked with container parameter set to `main`

#### Scenario: Custom container specified
- **WHEN** streaming logs with `--container wait`
- **THEN** the Kubernetes log streaming service is invoked with container parameter set to `wait`

### Requirement: Fallback pod resolution on not found error
When streaming logs for an unannotated workflow using default `v2` pod naming, if reading logs fails with an HTTP 404 Not Found error, the command SHALL fall back to `v1` pod name derivation.

#### Scenario: Fallback to v1 on 404
- **WHEN** log reading for a v2 pod name returns a 404 Not Found error
- **THEN** the command resolves pods using v1 naming and streams logs from the v1 pod
