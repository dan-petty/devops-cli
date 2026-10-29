# Tasks

## 1. The README describes the clusters as they run

- [x] Name both clusters in the intro and in Prerequisites, and state the storage layer of each
  - Verification: `uv run devops docs check`
- [x] Name the Alloy `alloy-logs` DaemonSet as the log shipper in the stacks table, and in `docs/DEVCONTAINER_USAGE.md`
  - Verification: `git grep -n -i fluent -- k8s docs/DEVCONTAINER_USAGE.md` returns nothing
- [x] Mark each `minikube service` command as minikube only and name the homelab Ingress host; use `kubectl port-forward` for the ClusterIP Services
  - Verification: `uv run devops docs check`
- [x] Say that Argo CD's `llm` Application deploys valkey-runs on the homelab
  - Verification: `uv run devops docs check`
- [x] State where the local-path provisioner keeps a volume, and which filesystem `LocalPathNodeDiskHigh` reads
  - Verification: `uv run pytest tests/test_k8s_local_path_placement.py tests/test_k8s_monitoring_alerting.py`

## 2. The values comments name both clusters

- [x] Rewrite the header and the minikube comments of `k8s/argocd/values.yaml`, `k8s/llm/values-open-webui.yaml`, `k8s/llm/values-qdrant.yaml` and `k8s/logging/loki-values.yaml`, and the tag comment of Open WebUI
  - Verification: `uv run pytest tests/invariants/test_k8s_manifests.py tests/test_k8s_qdrant_security.py tests/test_k8s_logging_stack.py tests/test_k8s_argocd_apps.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1648-k8s-readme-homelab`

## Workflow follow-up

- #2570: `devops devcontainer` enables the `storage-provisioner-rancher` addon of minikube, so the claims that name `local-path` bind.
- Pending a person: in dan-petty/homelab, decide whether `fast-nvme` names its base directory with `parameters.nodePath`, so that it keeps each volume on the faster disk.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
