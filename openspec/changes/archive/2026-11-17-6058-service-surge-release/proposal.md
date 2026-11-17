# Proposal: #6058

## Why
The roadmap Service deploys with `strategy: Recreate` and one replica. At each release the old pod drains for up to 600 s, and no pod gets the GitHub webhooks until the new pod is ready. On 2026-11-16, 5 of the 40 deliveries before 22:08Z got HTTP 503 during the rollout of release 0.169.1. GitHub does not send a failed delivery again, and the project ships about 19 releases a day. Closes #6058.

This change is step 1 of the split that the owner accepted on 2026-11-17. #4563 (state in Valkey), #4574 (the sweep) and #4575 (a stateless router with two replicas) are steps 2 to 4.

## What Changes
- The Deployment keeps one replica and rolls with `RollingUpdate`, `maxSurge: 1` and `maxUnavailable: 0`. The new pod shares the ReadWriteOnce volume on the same node. It gets the webhooks when `/readyz` passes, and only then does the old pod get SIGTERM.
- A preStop `sleep` of 10 s keeps the socket of the old pod open while its endpoint leaves the Service, because uvicorn closes its socket before the 600 s drain.
- The pod that holds the Kubernetes Lease `roadmap-service-rows` (`coordination.k8s.io/v1`) runs the rows. A pod reads its state files, removes the retired lane state, and starts its workers and the poll only when it holds the Lease. A pod that waits keeps each delivery in its lane queues and runs it when it takes the Lease. Readiness does not wait for the Lease. The pod gives the Lease back after its drain, and a killed holder loses it after 15 s.
- The Role of the Service gets `get` and `update` on the Lease `roadmap-service-rows`, and `create` on Leases, which RBAC cannot limit to a name.
- `service.instance.id` comes from the pod name, through the downward API.
- `docs/CLUSTER.md`, `docs/SERVICE_PATTERNS.md`, `docs/TELEMETRY.md` and `k8s/README.md` record the surge release and the RL1 exception: one replica, no PodDisruptionBudget, and a node drain still makes a gap (#4575).

## Capabilities
- `roadmap-service-deployment` (modified): the requirements "The Service rolls with a surge release" and "One pod of the Service holds the rows" replace "The Service runs as one pod".

## Impact
A release of the Service no longer stops the webhooks. A drain of the node still stops them until the new pod is ready on another node, and #4575 removes that gap. Each pod sends its own metric stream, so a new pod starts a new series, which `rate()` and `increase()` take as a counter reset. No setting is added or removed, and no credential is added.

## Feasibility
The comment of the owner of 2026-11-17 (issue comment 6933482788) accepts step 1 of the return of 2026-11-17 (comment 6933229420), whose table gives the singletons of the Service with `file:line`. The cluster runs k3s v1.37.2, which has the native preStop `sleep` action. The PV of `roadmap-service-home` binds to one node, and a ReadWriteOnce volume lets two pods on that node mount it. The Service already reaches the Kubernetes API with its projected token (`k8s/cluster_job_api.py`).

## Existing Tool Considered
The Lease API (`coordination.k8s.io/v1`) and the Deployment fields are the open tools. The official `kubernetes` client 36.0.3 of the project has a leader election with a ConfigMap lock only, a thread loop that does not stop, and no release. Client 37.0.2 adds a Lease lock and an asyncio loop, but it moves each model of the client to pydantic, and its loop also has no stop and no release. So `src/devops_cli/k8s/lease.py` applies the rules of the leader election of client-go in about 300 lines, with their docstrings, over the `CustomObjectsApi` seam that the fake cluster serves. The cost: about 150,000 model tokens and 4 hours. #4575 removes it.
