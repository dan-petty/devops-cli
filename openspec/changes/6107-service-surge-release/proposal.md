# Proposal: #6107

## Why
The roadmap Service rolls with `strategy: Recreate`, so each release stops the old pod, which drains for up to 600 s, before the new pod starts. While no pod is ready, GitHub webhook deliveries get HTTP 503, and GitHub does not send them again: 5 of 40 deliveries failed during the rollout of release 0.169.1, and the project ships about 19 releases a day. #6058 added the Lease `roadmap-service-rows`, so only one pod runs the rows. That release had to keep `Recreate`, because the pod before it had no Lease code. Now the Lease code runs, and the Service can roll with a surge. Closes #6107.

## What Changes
- `deployment/roadmap-service` rolls with `RollingUpdate`, `maxSurge: 1` and `maxUnavailable: 0`, and keeps one replica. The new pod starts beside the old pod, gets the webhooks when `/readyz` passes, and waits for the Lease while the old pod drains. Only then does the old pod get SIGTERM. The preStop sleep, `POD_NAME`, the instance id and the grace period of 660 s stay.
- The Deployment loses the kube-linter exception of `no-rolling-update-strategy`, so the `kube-linter` row of `devops ci` checks its strategy.
- The comment of the alert `RoadmapServiceUnavailable`, `docs/CLUSTER.md`, `docs/SERVICE_PATTERNS.md` (RL1) and `k8s/README.md` state the surge release, and the RL1 exception of one replica and no PodDisruptionBudget, so a drain of the node still stops the webhooks for a time (#4575).
- The manifest is observable behavior, so the change has a spec delta.

## Capabilities
- `roadmap-service-deployment` (modified): the requirement "The Service rolls with a surge release" replaces "The Service keeps Recreate until its Lease code runs".

## Impact
A release of the Service no longer stops the webhooks. During a release two pods run on the node of the home volume, for up to one drain of the old pod: each requests 100m of CPU and 768Mi of memory, and each sends its own metric stream. A drain of that node, or a restart of the pod, still stops the webhooks until the new pod is ready, and #4575 removes that gap. No setting is added or removed, and no credential is added. The change fits one pull request.

## Feasibility
- The Lease code runs. Release 0.170.0 carries #6058. On 2026-11-17 at 08:43Z, `kubectl -n devops get lease roadmap-service-rows -o jsonpath='{.spec.holderIdentity}'` named the running pod, and the Lease was renewed at that second (`renewTime`). The Deployment had one ready pod with `Recreate`.
- The PV of the claim `roadmap-service-home` has `nodeAffinity` `kubernetes.io/hostname In [<storage-node>]`, ReadWriteOnce, storage class `local-path` (`rancher.io/local-path`, `WaitForFirstConsumer`), and a `hostPath` source. The Deployment itself only keeps the pod off the control-plane node. The Kubernetes documentation of persistent volumes says: "Pods that use a PV will only be scheduled to nodes that are selected by the node affinity", and "ReadWriteOnce access mode still can allow multiple pods to access (read from or write to) that volume when the pods are running on the same node. For single pod access, please see ReadWriteOncePod." So the new pod lands on the node of the volume and mounts the claim beside the old pod.
- That node had 48% of its allocatable memory and 46% of its CPU requested, so it has room for a second pod.
- The code of #6058 reports ready without the Lease (`src/devops_cli/server/service.py`, the start of the rows manager), so the new pod gets ready and the rollout does not stop.
- `uv run devops k8s lint` passes with the exception removed.

## Existing Tool Considered
The Kubernetes Deployment `RollingUpdate` strategy covers the need. It is built in and maintained, and the change builds no code. The change deletes no internal code: it deletes the kube-linter exception annotation of the Deployment.
