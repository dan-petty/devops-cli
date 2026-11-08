# Tasks: Argo workflow for RAG index scheduling (#1653)

## 1. Manifests and network perimeter
- [x] 1.1 Add failing test for RAG ingest manifests, secret scoping, network policies, mutex, schedule, and embedding concurrency
  Verification: `$ uv run pytest tests/commands/k8s/test_k8s_rag_ingest_manifests.py`
- [x] 1.2 Create `k8s/devops/workflowtemplate-rag-ingest.yaml`, `k8s/devops/cronworkflow-rag-ingest.yaml`, and `k8s/devops/networkpolicy-rag-ingest.yaml`
  Verification: `$ kubectl kustomize k8s/devops`
- [x] 1.3 Update `k8s/llm/networkpolicy.yaml` with ingress rule for ingest pods on TCP port 6333
  Verification: `$ uv run pytest tests/commands/k8s/test_k8s_network_policies.py`
- [x] 1.4 Register manifests in `k8s/devops/kustomization.yaml`, `POST_HELM_BY_STACK`, and `MANIFESTS_BY_STACK`
  Verification: `$ uv run pytest tests/commands/k8s/test_k8s_devops_stack.py`

## 2. Secrets and telemetry
- [x] 2.1 Add `devops/qdrant-api-key` cluster secret definition in `src/devops_cli/k8s/cluster_secrets.py`
  Verification: `$ uv run pytest tests/commands/k8s/test_k8s_qdrant_security.py tests/k8s/test_cluster_secret_plan.py`
- [x] 2.2 Add `RAG_INGEST_LAST_SUCCESS_TIMESTAMP` instrument and emit freshness metric on success in `src/devops_cli/ai/rag/ingest.py`
  Verification: `$ uv run pytest tests/ai/rag/test_rag_ingest.py`
- [x] 2.3 Add `RagIngestBehind` alert to `k8s/monitoring/prometheus-values.yaml` and update alert tests
  Verification: `$ uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py`

## 3. Verification and gate
- [x] 3.1 Verify all manifest tests and deploy-stack dry run
  Verification: `$ uv run pytest tests/commands/k8s/test_k8s_rag_ingest_manifests.py`
- [x] 3.2 Run openspec check
  Verification: `$ uv run devops openspec check`

## Workflow follow-up
Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
