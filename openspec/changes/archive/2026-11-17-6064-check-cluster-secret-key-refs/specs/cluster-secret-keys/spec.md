# cluster-secret-keys Specification

## Purpose
The cluster Secret keys check: manifests and Helm values files under `k8s/` that reference a Secret of the generator table must reference only keys that have a row in that Secret's entries.

## ADDED Requirements

### Requirement: Unknown credential key fails the check
The check SHALL report a failure when a `secretKeyRef` names a key that the generator table of `devops k8s push-secrets` has no row for.

#### Scenario: Qdrant read-only key has no row
- **WHEN** The check gets a table with no `read-only-api-key` row for `llm/qdrant-api-key`, and `k8s/llm/values-qdrant.yaml` reads that key.
- **THEN** The check reports a failure that names the file, `llm/qdrant-api-key` and `read-only-api-key`.

### Requirement: Known credential key passes the check
The check SHALL pass when each `secretKeyRef` to a Secret of the generator table names a key of that Secret's row.

#### Scenario: Qdrant values as merged
- **WHEN** The table holds `api-key` and `read-only-api-key` for `llm/qdrant-api-key`, and `k8s/llm/values-qdrant.yaml` reads both keys.
- **THEN** The check reports no finding.

### Requirement: Secret outside the table is skipped
The check MUST skip a `secretKeyRef` whose Secret name is not a row of the generator table.

#### Scenario: Chart-made Secret
- **WHEN** A manifest under `k8s/` reads a key of a Secret that the generator table does not name.
- **THEN** The check reports no finding for that reference.

### Requirement: Cluster Secrets section names the live check
The Cluster Secrets section of `k8s/README.md` SHALL name `devops k8s push-secrets --only <namespace>/<name> --plan` and its `unchanged` result as a step before the merge.

#### Scenario: Cluster Secrets section names the plan check
- **WHEN** The documentation test reads the Cluster Secrets section of `k8s/README.md`.
- **THEN** The section contains the command and states to merge only when the plan shows `unchanged`.
