# Tasks

## 1. Validate the OpenSpec spec delta and cluster policies

Kind: other. Reads: `k8s/devops/searxng/networkpolicy.yaml`, `k8s/devops/searxng/networkpolicy-client.yaml`, `tests/gate/k8s_checks/network_policies.py`, `docs/CLUSTER.md`.

- [x] 1.1 Verify that `k8s/devops/searxng/networkpolicy-client.yaml` defines both `searxng-clients` and `searxng-stage-clients`, matching the `searxng-service` delta and `tests/gate/k8s_checks/network_policies.py`, and run `uv run devops ci --check --only openspec,docs,k8s`.
  - Verification: `$ uv run devops ci --check --only openspec,docs,k8s`
