# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for the Lease handover, a killed holder, a lost Lease, a waiting pod, and the stop on SIGTERM
  - Verification: `$ uv run devops ci test tests/k8s/test_lease.py tests/server/test_service_rows_lease.py tests/k8s/test_kubernetes_contract.py tests/roadmap/test_roadmap_run_service.py`
- [x] 1.2 Add the Lease holder, the Lease of the rows in the Service, the replace call of the fake, the preStop sleep and the Role rules, and keep `Recreate` until #6107
  - Verification: `$ uv run devops ci test tests/k8s/test_lease.py tests/server/test_service_rows_lease.py tests/k8s/test_kubernetes_contract.py tests/roadmap/test_roadmap_run_service.py`

## 2. Documents

- [x] 2.1 Record the two steps of the surge release, the Lease and the RL1 exception in `docs/CLUSTER.md`, `docs/SERVICE_PATTERNS.md` and `k8s/README.md`, and the instance id in `docs/TELEMETRY.md`
  - Verification: `$ uv run devops ci docs`
