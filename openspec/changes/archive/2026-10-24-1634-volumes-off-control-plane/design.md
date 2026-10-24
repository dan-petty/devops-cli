# Design

## Context

The cluster has four nodes. The control-plane node has the smallest root disk, and it also holds the model store of the slow Ollama tier, which only that node's GPU architecture serves. Both StorageClasses, `local-path` and `fast-nvme`, use the local-path provisioner with `WaitForFirstConsumer`: a volume is a directory on the root filesystem of the node where the first pod of its claim ran, and its node affinity holds every later pod of the claim on that node.

Argo CD tracks `main` with automated prune and self-heal. `cluster` is the parent of the Applications in `k8s/argocd/apps/`, and `bootstrap` is the parent of `cluster` and of itself.

## Goals / Non-Goals

**Goals:**

- Move the volumes on the control-plane node to worker nodes, with their data, and keep the old volumes until a person deletes them.
- Make a test fail when a pod that mounts a claim can run on the control-plane node.
- Warn before the disk of a node with local-path volumes reaches the kubelet's image GC threshold.
- Make `configure-urls --addressing proxy` correct after the move.

**Non-Goals:**

- A Retain StorageClass in dan-petty/homelab (remedy item 3) and more free space on the control-plane disk (remedy item 6). They are host and homelab-repository work, and they move to follow-up issues.
- A storage-role node label (remedy item 1). The standard control-plane label is enough.
- A delivery of the alert to a person. That needs the Alertmanager receiver Secret.

## Decisions

- **Decision: the standard control-plane label, as a required node affinity.**
  *Choice:* `node-role.kubernetes.io/control-plane` `DoesNotExist` in every term of `requiredDuringSchedulingIgnoredDuringExecution`, as #1967 does for the alloy-metrics claim.
  *Rejected alternative:* a storage-role label on the large-disk nodes, set by the homelab host configuration (the issue's remedy item 1).
  *Evidence for rejection:* every node but the control-plane node has a large disk (1 TB to 2 TB). A new label needs a host change and a second repository, and a node that misses it cannot take a volume.
  *Rejected alternative:* `preferredDuringSchedulingIgnoredDuringExecution`.
  *Evidence for rejection:* a preference lets the scheduler bind a new volume on the control-plane node when the workers are busy, and the binding is then permanent.

- **Decision: a table of chart claims in the test, not a chart render.**
  *Choice:* `CHART_CLAIMS` in the test names, for each chart that an Application installs, the values that turn a claim on (with the chart's default) and the values path of the affinity. A chart that the table does not name fails the test.
  *Rejected alternative:* `helm template` of each chart in the test.
  *Evidence for rejection:* the owner decided on 2026-10-24 that a test starts no program and reads no host state, and a render needs the chart from the network or a vendored copy of each chart.

- **Decision: exemptions for the three volumes that did not move.**
  *Choice:* Grafana, the Prometheus server and Loki are in `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` with their reason, and their values do not have the affinity yet. The test fails on an exemption for a pod that it does not find or that has the affinity, so the entry goes when the move is done.
  *Rejected alternative:* the affinity on the three values now.
  *Evidence for rejection:* the volumes of the three are on the control-plane node. A required affinity that excludes the node of the volume leaves the pod Pending, so the merge would stop Grafana, Prometheus and Loki.

- **Decision: copy with `kubectl exec` and GNU tar, and rebind by `claimRef`.**
  *Choice:* a destination pod pinned to a worker node with `nodeSelector` binds a new claim there. A source pod mounts the old claim read-only on the control-plane node. `tar` streams through the API server. Digests of the metadata and the content are compared. The new volume gets `Retain`, the temporary claim is deleted, the new volume's `claimRef` names the old claim with no `uid`, and the claim is made again from the saved one with `spec.volumeName`.
  *Rejected alternative:* `pv-migrate`.
  *Evidence for rejection:* see the proposal (a new binary, third-party images, and a NetworkPolicy opening for its `svc` strategy).
  *Rejected alternative:* one pod that mounts both claims.
  *Evidence for rejection:* the old volume holds a pod on the control-plane node, and the new claim binds on the node of its first pod, so a pod that mounts the two binds the new volume on the control-plane node too.

- **Decision: hold the workload with the top-down pause.**
  *Choice:* the procedure of `k8s/README.md`, Pausing an Application: `bootstrap`, `cluster`, then the child Application. After each move, the child Application is turned on again; after the last, `bootstrap`, which restores `cluster`.
  *Rejected alternative:* a pause in git (`enabled: false` merged on `main`).
  *Evidence for rejection:* an agent does not merge, and each merge would also sync every other change on `main`.

- **Decision: restore the saved `last-applied-configuration` annotation after the claim is made again.**
  *Choice:* the claim is created without the annotation, and a merge patch puts the saved value back.
  *Evidence:* after the Open WebUI move, Argo CD's sync failed with "PersistentVolumeClaim open-webui is invalid: spec is immutable after creation". `kubectl create` had written the whole new object, `volumeName` included, into the existing annotation, and Argo CD's three-way patch then removed `volumeName`. With the saved annotation back, the sync succeeded and the claim stayed bound.

- **Decision: `and` joins in `LocalPathNodeDiskHigh`.**
  *Choice:* `kube_pod_info and on (namespace, pod) (claims of the pod and on (namespace, persistentvolumeclaim) local-path claims)`, reduced to the node.
  *Rejected alternative:* the `group_left (node)` join that `LogOrMetricVolumeDiskLow` uses.
  *Evidence for rejection:* while the alloy-metrics pod moved, `kube_pod_info` had a series for each of two nodes, and Prometheus refused the `group_left` form with "many-to-many matching not allowed".

- **Decision: check each proxy address with one request.**
  *Choice:* `configure-urls --addressing proxy` sends `GET <proxy path>/` with no redirect, and does not write the address when the API server answers 503 with its own `ServiceUnavailable` Status. Any other answer, a redirect or the Service's own error included, means that the address works.
  *Rejected alternative:* read the EndpointSlices and the NetworkPolicies and predict the answer.
  *Evidence for rejection:* the result depends on the policy engine (kube-router admits the host network of the node itself), so a prediction from the objects can be wrong where one request is not.
  *Rejected alternative:* an `ipBlock` for the control-plane node in each perimeter.
  *Evidence for rejection:* it puts a private address of the cluster into git, and kube-router matches an `ipBlock` against pod addresses (`k8s/README.md`).
  *Rejected alternative:* a `k8s://` transport through the pod port-forward API.
  *Evidence for rejection:* every `k8s://` client, the Qdrant client included, takes a base URL and a prefix (`ProxyConnection`). A port-forward transport replaces that interface, which is far more than this item.
