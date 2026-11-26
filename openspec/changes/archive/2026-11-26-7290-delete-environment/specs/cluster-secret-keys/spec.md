## MODIFIED Requirements

### Requirement: Unknown credential key fails the check
The check SHALL report a failure when a `secretKeyRef` in a manifest or values file of the folder that it reads names a key that the generator table of `devops k8s push-secrets` has no row for.

#### Scenario: Qdrant read-only key has no row
- **WHEN** The check gets a table with no `read-only-api-key` row for `llm/qdrant-api-key`, and a values file of a fixture environment tree reads that key.
- **THEN** The check reports a failure that names the file, `llm/qdrant-api-key` and `read-only-api-key`.

### Requirement: Known credential key passes the check
The check SHALL pass when each `secretKeyRef` to a Secret of the generator table names a key of that Secret's row.

#### Scenario: Qdrant values as merged
- **WHEN** The table holds `api-key` and `read-only-api-key` for `llm/qdrant-api-key`, and a values file of a fixture environment tree reads both keys.
- **THEN** The check reports no finding.
