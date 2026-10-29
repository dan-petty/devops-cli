# Tasks

## 1. devops-cli's cache Valkey in the cluster

- [x] Add failing tests: the devops cache Valkey takes its password from its Secret, evicts the least recently used key at a bound below its limit, admits only namespace `devops` and the scrapers, and the ConfigMap and Secret `devops-cli` name it; and two intake runs with a shared Valkey send one embedding request
  - Verification: `uv run devops ci test tests/test_k8s_valkey_stack.py tests/test_roadmap_intake.py`
- [x] Add `k8s/llm/valkey-devops.yaml` with its Deployment, Service and `valkey-devops-perimeter`, list it in the llm kustomization and in deploy-stack's llm manifests, and leave its pods out of `llm-default-perimeter`
  - Verification: `uv run devops ci test tests/test_k8s_valkey_stack.py tests/test_k8s_network_policies.py tests/test_k8s_argocd_apps.py tests/test_k8s_monitoring_integration.py tests/test_k8s_llm_gateway.py`
- [x] Let namespace `devops` reach namespace `llm` on 6379, and set `valkey.url` in the devops ConfigMap template
  - Verification: `uv run devops ci test tests/test_k8s_devops_runtime.py tests/test_k8s_configmap.py`
- [x] Add `llm/valkey-devops-auth` and `DEVOPS_CLI_VALKEY_PASSWORD` of `devops/devops-cli` to the cluster secret table, and Secret `valkey-devops-auth` to the Argo CD project's ignored orphans
  - Verification: `uv run devops ci test tests/test_k8s_push_secrets.py tests/test_k8s_qdrant_security.py tests/test_k8s_argocd_apps.py`
- [x] Describe the Valkey, its perimeter, its bound and its two Secret rows in `k8s/README.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1655-intake-embedding-valkey`

## Workflow follow-up

- Pending a person: push the two Secrets before Argo CD starts the new pod: `devops k8s push-secrets --only llm/valkey-devops-auth --only devops/devops-cli`.
- Pending a person: once the Service runs, check that one intake candidate sends at most one embedding request and that `devops_cli_embedding_cache_lookups_total{tier="valkey",result="hit"}` rises.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
