# Tasks

## 1. Manifests

- [x] 1.1 Set `RollingUpdate` with `maxSurge: 1` and `maxUnavailable: 0` on `deployment/roadmap-service`, remove its kube-linter exception of `no-rolling-update-strategy`, and correct the comment of the alert `RoadmapServiceUnavailable`
  - Verification: `$ uv run devops ci --check --only k8s,kube-linter`

## 2. Documents

- [x] 2.1 State the surge release and the RL1 exception in `docs/CLUSTER.md`, `docs/SERVICE_PATTERNS.md` and `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4575 makes the webhook router stateless, with two replicas and a PodDisruptionBudget, and closes the gap of a node drain.
