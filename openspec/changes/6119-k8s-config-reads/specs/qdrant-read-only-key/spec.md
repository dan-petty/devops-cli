## MODIFIED Requirements

### Requirement: Qdrant reads a read-only key
The Qdrant container SHALL read its read-only key from key `read-only-api-key` of Secret `llm/qdrant-api-key`.

#### Scenario: The read-only key comes from the Secret
- **WHEN** a person runs `kubectl -n llm get statefulset qdrant -o yaml` on the cluster
- **THEN** the environment sets `QDRANT__SERVICE__READ_ONLY_API_KEY` from a `secretKeyRef` to that key, and it holds no literal value

### Requirement: The pod config names the Qdrant Service
The example ConfigMap SHALL name `qdrant.url` as the Qdrant Service of namespace `llm` on TCP 6333, and it SHALL hold no key value.

#### Scenario: The template names the in-cluster URL
- **WHEN** `uv run devops k8s deploy-stack --stack devops --dry-run` renders ConfigMap `devops-cli-config` from the template
- **THEN** `qdrant.url` is `http://qdrant.llm.svc.cluster.local:6333`, and the `qdrant` section holds no `api_key` value
