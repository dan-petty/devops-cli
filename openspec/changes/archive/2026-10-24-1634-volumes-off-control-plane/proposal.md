# Proposal

## Why

Issue #1634: six of the bound local-path volumes, 60Gi claimed, were on the root disk of the control-plane node. That disk is 236 GB and 84% used (`1 - available/size`), and the three worker nodes have 1 TB to 2 TB disks at 13% to 17%. Nothing in git steered placement. local-path binds a volume on the node where the first pod of its claim runs, and the volume then holds its pod on that node. At 85% the kubelet starts image garbage collection, and under DiskPressure it evicts pods that cannot start on another node, on the node that also runs the API server.

The owner chose on 2026-10-24 to copy the six volumes to worker nodes, to keep 30 days of metrics and logs, the Grafana and Open WebUI data and the Qdrant index. The lead chose the placement rule: each pod that mounts a local-path claim has the required node affinity `node-role.kubernetes.io/control-plane` `DoesNotExist`, the label that Kubernetes puts on each control-plane node. No new node label and no host change.

## What Changes

- Copy the volumes of Pyroscope, Qdrant and Open WebUI from the control-plane node to worker nodes, one at a time, with the data checked on both sides. The old volumes stay, with reclaim policy `Retain`, until a person deletes them. The copies of Grafana, Prometheus and Loki did not run: the permission system of the agent session refused the scale to zero of Grafana. Their old volumes have reclaim policy `Retain`.
- Add `tests/test_k8s_local_path_placement.py`. It fails when a pod that mounts a claim, in a chart values file or a manifest under `k8s/`, has no required node affinity with the control-plane `DoesNotExist` term in each term. It also fails when an Argo CD Application installs a chart that the test does not know, and on a stale exemption.
- Add the affinity to Open WebUI, Qdrant, Pyroscope, Tempo, Alertmanager, `valkey-runs` and `roadmap-service`. The alloy-metrics claim of #1967 already has it.
- Add `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` to `src/devops_cli/config/constants.py`, with Grafana, the Prometheus server and Loki. Their volumes are still on the control-plane node, and with the affinity their pods could not start.
- Add the alert `LocalPathNodeDiskHigh` to `k8s/monitoring/prometheus-values.yaml`: a warning when the root filesystem of a node that runs a pod on a `local-path` claim is over 85% used for 15 minutes, with its test entries.
- `devops k8s configure-urls --addressing proxy` sends one GET of the Service root through the API server for each address, and writes only the addresses that the Service answers. When the API server answers with its own `ServiceUnavailable` Status, the command writes nothing for that key and names `--addressing fqdn` and `devops k8s port-forward`. The new public function `reaches_service` in `src/devops_cli/k8s/service_http.py` makes the check.
- Document the placement rule, the exemptions, the alert and the copy procedure in `k8s/README.md` (Local-Path Volume Placement), and correct the `--addressing proxy` bullet and the help text of `--addressing`.
- The manifests, the alert and the command output are observable behavior, so the change has spec deltas: the new capabilities `local-path-volume-placement` and `cluster-service-addressing`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `local-path-volume-placement`: where the pods on local-path claims run, and the warning before the disk of a node with local-path volumes fills.
- `cluster-service-addressing`: which `k8s://` addresses `configure-urls --addressing proxy` writes.

### Modified Capabilities

None.

## Impact

- `k8s/llm/values-open-webui.yaml`, `k8s/llm/values-qdrant.yaml`, `k8s/monitoring/pyroscope-values.yaml`, `k8s/otel/tempo-values.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/llm/valkey-runs.yaml`, `k8s/devops/roadmap-service/deployment.yaml`.
- `src/devops_cli/config/constants.py`, `src/devops_cli/k8s/service_http.py`, `src/devops_cli/commands/k8s/networking.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, and the generated `docs/commands/k8s.md` and `docs/CLI_REFERENCE.md`.
- `tests/test_k8s_local_path_placement.py`, `tests/test_k8s_proxy_reachability.py`, `tests/test_k8s_monitoring_alerting.py`, `tests/test_k8s_proxy_addressing.py`, `tests/test_config_field_validation.py`.
- `k8s/README.md`.
- The live cluster after the merge: Argo CD restarts the pods whose values change. Each one stays on its node, because its volume holds it there and the node is a worker node. Grafana, the Prometheus server and Loki do not change.

## Feasibility

Checked on 2026-10-24 against the homelab cluster (k3s v1.31.4, Argo CD v3.5.3, local-path provisioner):

- Disks. `/api/v1/nodes/<node>/proxy/stats/summary`: the control-plane node has 236.2 GB, 185.8 GB used, 38.3 GB available (83.8% by `1 - available/capacity`, the kubelet's measure). The worker nodes have 1967.5 GB, 1967.5 GB and 1006.7 GB, 13.2% to 16.9% used.
- Volumes. `kubectl get pv`: `data-pyroscope-0`, `qdrant-storage-qdrant-0`, `open-webui`, `grafana`, `prometheus-server` and `storage-loki-0` had node affinity to the control-plane node. Tempo, Alertmanager, `valkey-runs-data` and `roadmap-service-home` were on a worker node already.
- The label. `kubectl get nodes --show-labels`: only the control-plane node has `node-role.kubernetes.io/control-plane=true`, and no node has a taint. #1967 uses the same `DoesNotExist` term for the alloy-metrics claim.
- Chart keys. `helm show values` of each pinned chart: `affinity` (grafana 14.0.1, qdrant 1.19.1, tempo 3.1.0, open-webui 16.6.0), `server.affinity` and `alertmanager.affinity` (prometheus 29.35.0), `pyroscope.affinity` (pyroscope 2.3.1), `singleBinary.affinity` (loki 7.3.0). `helm template` with the changed values puts the term on the StatefulSets of Qdrant, Open WebUI, Tempo, Pyroscope and Alertmanager.
- Holding a workload at zero. `k8s/README.md` (Pausing an Application) documents the pause from the top down: `bootstrap`, `cluster`, then the Application. A paused `bootstrap` stayed paused, and `kubectl scale --replicas=0` held while the child Application was paused.
- Proxy addressing. `kubectl get --raw /api/v1/namespaces/<namespace>/services/<service>:<port>/proxy/`: Prometheus, Grafana and Qdrant on the control-plane node answered. Alertmanager and Tempo on a worker node behind a perimeter got `503` with a `Status` of reason `ServiceUnavailable` ("error trying to reach service"). The path without the last `/` gets `301` from the API server itself, so the check asks for `/`.
- The alert expression. Prometheus evaluated it through Grafana: it returned the root filesystem of the three nodes with pods on local-path claims (0.84, 0.13, 0.18 used) and not the node without them. A first form with `group_left` on `kube_pod_info` failed with "many-to-many matching not allowed" while the alloy-metrics pod moved between nodes, so the joins are `and`.
- The moves, with the result of each, are in `tasks.md`.

## Existing Tool Considered

- Volume copy: `pv-migrate` (utkuozdemir/pv-migrate) copies a claim to another claim with rsync. It needs a new binary on the workstation, its sshd and rsync images from its own registry, and for its `svc` strategy a NetworkPolicy opening between its pods in each namespace behind a perimeter. For six volumes of 0.5 GB to 2 GB, `kubectl exec` with GNU tar from the stock `debian:trixie-slim` image does the same copy through the API server, where no NetworkPolicy applies, with tools that are already there. The change adds no copy code to the repository.
- Placement: the standard Kubernetes node affinity and the standard control-plane label. No scheduler plugin and no new label.
- The alert: a Prometheus rule over series that kube-state-metrics and node-exporter already serve.
- The reachability check: the API server's own `Status` answer and the HTTP client that `get_json` already uses. It adds one function of about 20 lines and no dependency.

The change deletes the legacy tests `test_proxy_mode_records_portable_addresses` and `test_proxy_addressing_survives_round_trip`, which patched discovery and wrote each address with no check. `tests/test_k8s_proxy_reachability.py` replaces them.
