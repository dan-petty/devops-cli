# Tasks

## 1. The Kubernetes API seam, its shared fake and its contract suite

- [x] Add failing tests: the `cluster` fixture serves the service from the fake; the fake answers a missing object with `ApiException(404)`, refuses every call when unreachable and records each call; the contract cases run each Protocol call over the fake and over the real client against recorded responses (list and read results, a 404 and a 403, a watch stream, an unreachable server)
  - Verification: `uv run devops ci test tests/k8s/test_kubernetes_contract.py`
- [x] Add `k8s/api.py` with the Protocols, `KubernetesApis`, `KubernetesApiSource` and `KubernetesClientSource` with its one configuration rule; make `KubernetesService` take a source, add `install`, `core_api` and the source-backed `custom_objects_api`, and delete `_get_kubeconfig_path` and the `AppsV1Api` client
  - Verification: `uv run devops ci test tests/k8s/ tests/test_k8s_service.py`
- [x] Make `switch_context` check the context and realign the clients without writing the kubeconfig
  - Verification: `uv run devops ci test tests/test_k8s_service.py`
- [x] Use `core_api` in `k8s/informer.py` and `k8s/service_proxy.py`, so no module reads a private attribute of the service
  - Verification: `uv run devops ci test tests/test_k8s_service.py tests/test_k8s_service_proxy.py`
- [x] Promote `tests/k8s_fakes.py` to `tests/support/fakes/kubernetes.py`, delete it, and change only the import of its importers
  - Verification: `uv run devops ci test tests/test_k8s_doctor.py tests/test_k8s_models.py tests/test_k8s_volume_reclaim.py tests/test_k8s_logs_diff_chaos.py tests/test_ui_dashboard.py tests/test_ui_reactive.py`
- [x] Move `tests/test_k8s_service.py` onto the fake, the real source over a kubeconfig in `tmp_path`, and the contract suite, so it patches no `kubernetes` name and no method of the service
  - Verification: `uv run devops ci test tests/test_k8s_service.py`
- [x] Describe the Kubernetes fake and its contract suite in `docs/TESTING.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1315-kubernetes-api-seam`
- Pending a person: capture the recorded responses in `tests/fixtures/kubernetes/` once from a disposable local cluster, scrubbed to `example.com` names and documentation-range addresses, and commit them with the commands that captured them.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

## Workflow follow-up

- #1322 routes `k8s/service_proxy.py` and `k8s/doctor.py` through the seam.
- #1323 routes `commands/k8s/cluster_context.py` through the seam.
- #1334 routes `ui/data_providers.py` through the seam.
