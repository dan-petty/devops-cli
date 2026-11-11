# Tasks

## 1. The pod specs

- [x] 1.1 Add the check `tests/gate/k8s_checks/telemetry_resource.py` and the test of the two names in `tests/telemetry/test_telemetry.py`, and see the check fail on the old manifests
  - Verification: `$ uv run devops ci --only k8s`
- [x] 1.2 Set `K8S_CONTEXT` and `POD_NAMESPACE` in the 5 devops-cli containers of `k8s/devops/`
  - Verification: `$ uv run devops ci --only k8s`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py`

## 2. Documents

- [x] 2.1 Describe the two values in `k8s/README.md` (section devops-cli in the cluster)
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after Argo CD syncs the change, run the TraceQL `{ resource.service.name = "roadmap-service" } | count_over_time() by (resource.k8s.cluster.name)` and see `homelab-k3s` for the new spans.
