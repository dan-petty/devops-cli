# qdrant-read-only-key Specification

## Purpose
The Qdrant read-only key: Qdrant serves its read-only key from Secret `llm/qdrant-api-key`, the pods that load Secret `devops/devops-cli` with `envFrom` and set no Qdrant key of their own hold that key, and one keyring value feeds both Secrets.

## Requirements

### Requirement: Qdrant reads a read-only key
The Qdrant container SHALL read its read-only key from key `read-only-api-key` of Secret `llm/qdrant-api-key`.

#### Scenario: The read-only key comes from the Secret
- **WHEN** a person runs `kubectl -n llm port-forward svc/qdrant 6333:6333`, and sends a search and an upsert to a collection on the local port with the read-only key in the `api-key` header
- **THEN** Qdrant answers the search with 200 and refuses the upsert with 403

### Requirement: One keyring value feeds both Secrets
The push SHALL write one keyring value, `qdrant_read_only_api_key`, to key `read-only-api-key` of Secret `llm/qdrant-api-key` and to `DEVOPS_CLI_QDRANT_API_KEY` of Secret `devops/devops-cli`.

#### Scenario: The table holds two rows from one keyring value
- **WHEN** a test reads the rows of `src/devops_cli/k8s/cluster_secrets.py`
- **THEN** the two rows both name keyring `qdrant_read_only_api_key`, and the devops row adopts from `llm/qdrant-api-key read-only-api-key`

### Requirement: The runner holds no write path
The runner pod SHALL hold no Qdrant key (#6518). A pod that loads Secret `devops/devops-cli` with `envFrom` and sets no `DEVOPS_CLI_QDRANT_API_KEY` of its own, such as a Job of CronJob `devops-cli`, SHALL get its Qdrant key from the read-only key, and no row of Secret `devops/devops-cli` SHALL name the admin key `api-key`.

#### Scenario: The runner template holds no Qdrant key
- **WHEN** `uv run devops ci --check --only k8s` renders CronJob `devops-cli-runner`
- **THEN** its container has no `envFrom` and no `DEVOPS_CLI_QDRANT_API_KEY`

#### Scenario: The Secret holds only the read-only key
- **WHEN** `uv run devops ci --check --only k8s` runs, and a person runs `uv run devops k8s push-secrets --stack devops --dry-run`
- **THEN** the row passes only when WorkflowTemplate `rag-ingest` is the one object of `k8s/devops` that names the Secret of the admin key
- **AND** the dry run writes `DEVOPS_CLI_QDRANT_API_KEY` of Secret `devops/devops-cli` from keyring `qdrant_read_only_api_key`, and from no other keyring entry
