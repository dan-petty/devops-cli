# Tasks

## 1. Share the readers of the k8s tree

- [x] 1.1 Move the readers of `tests/test_k8s_local_path_placement.py` into `tests/support/k8s_tree.py`, and delete the private copies. The readers give the value at a dotted path, the YAML documents of a file and the values of each chart that an Application installs. They also give the objects of each manifest and the pod spec of a workload. Verify with `uv run devops ci test tests/test_k8s_local_path_placement.py`.

## 2. Pods that do not call the API mount no token

- [x] 2.1 Write the failing tests in `tests/invariants/test_k8s_manifests.py`, and see them fail with `uv run devops ci test tests/invariants/test_k8s_manifests.py`. The tests check these rules:
  - The pod field wins over the ServiceAccount field, and a volume that holds a token is a token.
  - The table names each chart at the version that its Application pins.
  - The readers see each value and each patch that reaches a checked object.
  - Each manifest pod and chart pod has no token, or has a role.
  - No exception is stale.
- [x] 2.2 Add `automountServiceAccountToken: false` to the pod templates of `cloudflared`, `gpu-feature-discovery`, `llm-gateway`, `portkey`, `valkey`, `valkey-runs` and the nine Ollama tiers. Turn the token off in the values of Loki, Tempo, the OpenTelemetry collector and Alertmanager. Do the same for the Argo CD repo server and Redis, and for Gitea. Add the table `_TOKEN_EXCEPTIONS` of the test with Qdrant and the CoreDNS patch. Move `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` into `tests/test_k8s_local_path_placement.py`. Verify with `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/test_k8s_local_path_placement.py tests/test_k8s.py tests/test_k8s_gitea.py tests/test_k8s_tempo.py tests/test_k8s_argo_workflows.py tests/test_k8s_valkey_stack.py tests/test_k8s_llm_gateway.py tests/test_k8s_gpu_placement.py`.
- [x] 2.3 Document the rule and the exceptions in `k8s/README.md` (Service Account Tokens). Verify with `uv run devops docs check`.

## Workflow follow-up

- Pending a person: after Argo CD syncs the merge, `kubectl get pods -A -o json` shows no `kube-api-access-*` volume on the pods that lost their token. These are the pods of `cloudflared`, `gpu-feature-discovery`, `llm-gateway`, `portkey`, `valkey`, `valkey-runs` and the Ollama tiers. They are also `loki-0`, `tempo-0`, `prometheus-alertmanager-0`, the OpenTelemetry collector, `argocd-repo-server`, `argocd-redis` and `gitea`. `kubectl get pods -A` shows each of them Ready.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
