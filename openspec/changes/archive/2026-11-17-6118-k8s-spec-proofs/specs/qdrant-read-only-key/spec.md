## MODIFIED Requirements

### Requirement: Qdrant reads a read-only key
The Qdrant container SHALL read its read-only key from key `read-only-api-key` of Secret `llm/qdrant-api-key`.

#### Scenario: The read-only key comes from the Secret
- **WHEN** a person runs `kubectl -n llm port-forward svc/qdrant 6333:6333`, and sends a search and an upsert to a collection on the local port with the read-only key in the `api-key` header
- **THEN** Qdrant answers the search with 200 and refuses the upsert with 403

### Requirement: The runner holds no write path
The runner pod SHALL get its Qdrant key from the read-only key, and no row of Secret `devops/devops-cli` SHALL name the admin key `api-key`.

#### Scenario: The runner template reads the read-only key
- **WHEN** `uv run devops ci --check --only k8s` runs, and a person runs `uv run devops k8s push-secrets --stack devops --dry-run`
- **THEN** the row passes only when WorkflowTemplate `rag-ingest` is the one object of `k8s/devops` that names the Secret of the admin key
- **AND** the dry run writes `DEVOPS_CLI_QDRANT_API_KEY` of Secret `devops/devops-cli` from keyring `qdrant_read_only_api_key`, and from no other keyring entry

## REMOVED Requirements

### Requirement: The pod config names the Qdrant Service
**Reason**: The requirement restates a value of the example ConfigMap `k8s/devops/configmap.example.yaml`, and only a test that reads the file can check it. No Application renders that file: deploy-stack renders the ConfigMap from the active config (#6083).
**Migration**: None. The requirement "Qdrant reads a read-only key" proves the key on the cluster.

### Requirement: The documentation names the key and the person step
**Reason**: The requirement restates rows of the secret table in `k8s/README.md` and a rule of `SECURITY.md`, and only a test that reads the documents can check it (#6083).
**Migration**: The requirement "One keyring value feeds both Secrets" holds the rows, and a test of the source code checks the table.
