# Proposal

## Why

Issue #1648: `k8s/README.md` and four values files describe a cluster that does not run.

- The README names Fluent Bit as the log shipper. #548 removed it, and Alloy ships the logs.
- It names only the devcontainer's minikube as the target. The cluster that Argo CD keeps in line with `main` is the k3s homelab.
- Its access commands are `minikube service` commands, with no homelab way to reach each service. Two of them name ClusterIP Services, which `minikube service` cannot open.
- Its Prerequisites do not say where the storage layer comes from.
- It says that the local-path provisioner keeps a volume on its node's root filesystem.
- The values files of Argo CD, Open WebUI, Qdrant and Loki call themselves minikube configurations, and the Open WebUI file names a floating `main` tag next to a pinned tag.

## What Changes

- The README intro names both clusters: the k3s homelab, which Argo CD keeps in line with `main`, and the devcontainer's minikube. `devops k8s deploy-stack` deploys to either.
- The Loki row of the stacks table names the Alloy `alloy-logs` DaemonSet, which ships the pod and journal logs.
- Prerequisites name both clusters and the storage layer:
  - On the homelab, dan-petty/homelab's `make storage` applies the local-path provisioner and the StorageClasses `local-path` (default, `Delete`) and `fast-nvme` (`Retain`), and k3s runs with its bundled local-path storage turned off.
  - On minikube, the class `local-path` needs the `storage-provisioner-rancher` addon, which `devops devcontainer` does not enable (#2570).
- Each access command says whether it works only on minikube, and names the homelab Ingress host of the service. The Alloy metrics and Qdrant commands use `kubectl port-forward`, because their Services are ClusterIP.
- The valkey-runs comment says that Argo CD's `llm` Application deploys it on the homelab.
- Local-Path Volume Placement says where the provisioner keeps a volume: under one of two base directories of the node, at random, because neither StorageClass names one. `fast-nvme` thus differs from `local-path` only by its reclaim policy. The paragraph names the filesystem that `LocalPathNodeDiskHigh` reads.
- The values comments of Argo CD, Open WebUI, Qdrant and Loki name both clusters and the homelab Ingress, and the Open WebUI tag comment says that the tag is pinned.
- `docs/DEVCONTAINER_USAGE.md` no longer names Fluent Bit.
- The change alters documents and comments only, so it has no spec delta and sets `skip_specs: true`.
- This change fits one pull request.

## Impact

- `k8s/README.md`, `docs/DEVCONTAINER_USAGE.md`.
- Comments in `k8s/argocd/values.yaml`, `k8s/llm/values-open-webui.yaml`, `k8s/llm/values-qdrant.yaml` and `k8s/logging/loki-values.yaml`.

## Feasibility

Each fact was read on 2026-10-28 from the live homelab (read-only) or from upstream source:

- Four nodes, one control-plane and three workers, run kubelet `v1.31.4+k3s1`. No pod name has `fluent`. DaemonSet `monitoring/k8s-monitoring-alloy-logs` runs on all 4 nodes, and Loki runs as StatefulSet `logging/loki`. `k8s/monitoring/k8s-monitoring-values.yaml` (`podLogs`, `nodeLogs`) reads the pod logs and each node's journal.
- Deployment `llm/valkey-runs` has the tracking id `llm:apps/Deployment:llm/valkey-runs`, and Application `llm` (path `k8s/llm`) is Synced. `devops k8s deploy-stack --stack llm` applies `llm/valkey-runs.yaml` too (`commands/k8s/stack_lifecycle.py`).
- The StorageClasses `local-path` (default, `Delete`) and `fast-nvme` (`Retain`) use `rancher.io/local-path` with `WaitForFirstConsumer`. The provisioner `rancher/local-path-provisioner:v0.0.28` runs in namespace `local-path-storage`. The k3s addon list has no `local-storage`. dan-petty/homelab `k8s/manifests/local-path-storage.yaml` declares those objects, and its Makefile target `storage` applies that file.
- ConfigMap `local-path-config` gives the default node entry two base paths, one under `/var` and one under `/mnt`. No StorageClass sets `parameters.nodePath`. In `provisioner.go` of local-path-provisioner v0.0.28, `getPathOnNode` returns a random path of the set when no path is requested. On 2026-10-28 one live volume, the `alloy-wal` claim of `alloy-metrics`, was under the `/mnt` path.
- Services `argocd/argocd-server`, `llm/open-webui`, `llm/llm-gateway` and `llm/valkey-runs` are NodePort. `monitoring/k8s-monitoring-alloy-metrics` (port 12345) and `llm/qdrant` (port 6333) are ClusterIP. `ingress/ingress-routes.yaml` holds the Ingresses `argocd-ingress`, `alloy-metrics-ingress`, `open-webui-ingress`, `qdrant-ingress` and `llm-gateway-ingress`, and the live hosts have the form `<name>.<domain>`. `argocd-ingress` uses Traefik's `web` entrypoint to port 80.
- minikube v1.39.0 lists the addons `default-storageclass`, `storage-provisioner` and `storage-provisioner-rancher`. `_start_minikube` (`commands/k8s/cluster_runtime.py`) enables none. So the issue's proposed sentence "on minikube the bundled provisioner serves `local-path`" is not true, and the README states the addon step instead (#2570).

## Existing Tool Considered

The change is documentation. It names the tools that give each fact: Argo CD, the Alloy `alloy-logs` DaemonSet, the rancher local-path provisioner and minikube's `storage-provisioner-rancher` addon. It builds no code and deletes no code.
