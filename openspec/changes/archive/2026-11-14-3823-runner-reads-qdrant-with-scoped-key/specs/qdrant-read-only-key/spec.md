## ADDED Requirements

### Requirement: Qdrant reads a read-only key
The Qdrant container SHALL read its read-only key from key `read-only-api-key` of Secret `llm/qdrant-api-key`.

#### Scenario: The read-only key comes from the Secret
- **WHEN** a test reads `k8s/llm/values-qdrant.yaml`
- **THEN** the environment sets `QDRANT__SERVICE__READ_ONLY_API_KEY` from a `secretKeyRef` to that key, and it holds no literal value

### Requirement: One keyring value feeds both Secrets
The push SHALL write one keyring value, `qdrant_read_only_api_key`, to key `read-only-api-key` of Secret `llm/qdrant-api-key` and to `DEVOPS_CLI_QDRANT_API_KEY` of Secret `devops/devops-cli`.

#### Scenario: The table holds two rows from one keyring value
- **WHEN** a test reads the rows of `src/devops_cli/k8s/cluster_secrets.py`
- **THEN** the two rows both name keyring `qdrant_read_only_api_key`, and the devops row adopts from `llm/qdrant-api-key read-only-api-key`

### Requirement: The runner holds no write path
The runner pod SHALL get its Qdrant key from the read-only key, and no row of Secret `devops/devops-cli` SHALL name the admin key `api-key`.

#### Scenario: The runner template reads the read-only key
- **WHEN** a test reads `k8s/devops/cronjob-runner.yaml` and the rows of Secret `devops/devops-cli`
- **THEN** `DEVOPS_CLI_QDRANT_API_KEY` comes from keyring `qdrant_read_only_api_key`, and no row of `devops/devops-cli` names keyring `qdrant_api_key`

### Requirement: The pod config names the Qdrant Service
The example ConfigMap SHALL name `qdrant.url` as the Qdrant Service of namespace `llm` on TCP 6333, and it SHALL hold no key value.

#### Scenario: The template names the in-cluster URL
- **WHEN** a test reads `k8s/devops/configmap.example.yaml`
- **THEN** `qdrant.url` is `http://qdrant.llm.svc.cluster.local:6333`, and the `qdrant` section holds no `api_key` value

### Requirement: The documentation names the key and the person step
The documentation SHALL name the read-only key and the command that a person runs to push it.

#### Scenario: The Cluster Secrets table holds the rows
- **WHEN** a test reads the Cluster Secrets section of `k8s/README.md` and rule 1 of `SECURITY.md`
- **THEN** the section lists both rows from keyring `qdrant_read_only_api_key` with `devops k8s push-secrets` as the person step, and rule 1 names the read-only Qdrant key of the runner
