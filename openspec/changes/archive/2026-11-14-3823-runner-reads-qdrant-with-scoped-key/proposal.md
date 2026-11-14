# Proposal: #3823

## Why

The runner pod cannot reach Qdrant. `k8s/devops/networkpolicy.yaml` admits egress to namespace `llm` on TCP 4000 and 6379 only, and Qdrant answers on 6333. So the implement agent cannot use the RAG index (#3563, item B). The change opens the Qdrant search path with a read-only key, and adds no write or delete path.

## What Changes

- `k8s/devops/networkpolicy.yaml` gains one egress rule to namespace `llm` on TCP 6333, and no other peer or port.
- `k8s/llm/networkpolicy.yaml` gains one ingress rule from namespace `devops` on TCP 6333.
- `k8s/llm/values-qdrant.yaml` reads key `read-only-api-key` of Secret `llm/qdrant-api-key` as `QDRANT__SERVICE__READ_ONLY_API_KEY`.
- `src/devops_cli/k8s/cluster_secrets.py` adds key `read-only-api-key` to Secret `llm/qdrant-api-key` and `DEVOPS_CLI_QDRANT_API_KEY` to Secret `devops/devops-cli`, both from keyring `qdrant_read_only_api_key`.
- `k8s/devops/configmap.example.yaml` names `qdrant.url` as `http://qdrant.llm.svc.cluster.local:6333` and holds no key.
- `k8s/README.md` names the route, the two Secret rows and the person step. `SECURITY.md` rule 1 names the read-only key of the runner.
- Tests pin the two policy rules, the Qdrant values, the two Secret rows, the ConfigMap and the README.

## Capabilities

- `k8s-network-policies`
- `qdrant-read-only-key`

## Impact

The runner and the roadmap Service reach Qdrant for search. A person creates the read-only key in the keyring and pushes it; the change makes no Secret value. The ingest workflow keeps the admin key.

## Feasibility

Checked on `origin/main` 5fbcd0519, 2026-11-14. `devops-default-perimeter` selects every `devops` pod but the Crawl4AI and SearXNG pods, and the runner Jobs carry the label `app.kubernetes.io/name: devops-cli-job`. Qdrant requires a key on every REST and gRPC request. The Qdrant chart renders `env` on the container and declares no `readOnlyApiKey` Secret of its own. `uv run devops ci test tests/commands/k8s/test_k8s_network_policies.py tests/commands/k8s/test_k8s_qdrant_security.py tests/config/test_k8s_devops_runtime.py` passes.

## Existing Tool Considered

The Kubernetes NetworkPolicy API and the Qdrant read-only API key cover the need. No new tool, and no build code. The read-only key permits every read of the instance, and refuses write and delete. A JWT RBAC token scopes to one collection, and it needs the `jwt_rbac` setting and a token that a person mints.
