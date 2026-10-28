# Tasks

## 1. Share the readers of the k8s tree

- [x] 1.1 Move the readers of `tests/test_k8s_local_path_placement.py` (the values at a dotted path, the YAML documents of a file, the values of each chart that an Application installs, the objects of each manifest, and the pod spec of a workload) into `tests/support/k8s_tree.py`, and delete the private copies; verify with `uv run devops ci test tests/test_k8s_local_path_placement.py`

## 2. Pods that do not call the API mount no token

- [ ] 2.1 Write the failing tests in `tests/invariants/test_k8s_manifests.py` (the pod field wins over the ServiceAccount field, every chart known, every manifest pod and chart pod without a token or with a role, no stale exception), and see them fail with `uv run devops ci test tests/invariants/test_k8s_manifests.py`
- [ ] 2.2 Add `automountServiceAccountToken: false` to the pod templates of `cloudflared`, `gpu-feature-discovery`, `llm-gateway`, `portkey`, `valkey`, `valkey-runs` and the nine Ollama tiers; turn the token off in the values of Loki, Tempo, the OpenTelemetry collector, Alertmanager, the Argo CD repo server and Redis, and Gitea; add `CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS` with Qdrant and the CoreDNS patch. Verify with `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/test_k8s_local_path_placement.py tests/test_k8s.py tests/test_k8s_gitea.py tests/test_k8s_tempo.py tests/test_k8s_argo_workflows.py tests/test_k8s_valkey_stack.py tests/test_k8s_llm_gateway.py tests/test_k8s_gpu_placement.py`
- [ ] 2.3 Document the rule and the exceptions in `k8s/README.md` (Service Account Tokens); verify with `uv run devops docs check`

## Workflow follow-up

- Pending a person: after Argo CD syncs the merge, `kubectl get pods -A -o json` shows no `kube-api-access-*` volume on the pods of `cloudflared`, `gpu-feature-discovery`, `llm-gateway`, `portkey`, `valkey`, `valkey-runs`, the Ollama tiers, `loki-0`, `tempo-0`, `prometheus-alertmanager-0`, the OpenTelemetry collector, `argocd-repo-server`, `argocd-redis` and `gitea`, and `kubectl get pods -A` shows each of them Ready.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
