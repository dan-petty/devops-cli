## MODIFIED Requirements

### Requirement: The runner holds no write path
The runner pod SHALL hold no Qdrant key (#6518). A pod that loads Secret `devops/devops-cli` with `envFrom`, such as a Job of CronJob `devops-cli`, SHALL get its Qdrant key from the read-only key, and no row of Secret `devops/devops-cli` SHALL name the admin key `api-key`.

#### Scenario: The runner template holds no Qdrant key
- **WHEN** `uv run devops ci --check --only k8s` renders CronJob `devops-cli-runner`
- **THEN** its container has no `envFrom` and no `DEVOPS_CLI_QDRANT_API_KEY`

#### Scenario: The Secret holds only the read-only key
- **WHEN** `uv run devops ci --check --only k8s` runs, and a person runs `uv run devops k8s push-secrets --stack devops --dry-run`
- **THEN** the row passes only when WorkflowTemplate `rag-ingest` is the one object of `k8s/devops` that names the Secret of the admin key
- **AND** the dry run writes `DEVOPS_CLI_QDRANT_API_KEY` of Secret `devops/devops-cli` from keyring `qdrant_read_only_api_key`, and from no other keyring entry
