# Tasks

## 1. The devops perimeter opens only OTLP/HTTP to the collector

- [x] Add a failing test: the egress rule of the devops perimeter to the `otel` namespace names the one port TCP 4318
  - Verification: `uv run devops ci test tests/test_k8s_network_policies.py`
- [x] Remove TCP 4317 from that rule of `k8s/devops/networkpolicy.yaml`
  - Verification: `uv run devops ci test tests/test_k8s_network_policies.py` and `kubectl apply --dry-run=server -f k8s/devops/networkpolicy.yaml`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2548-devops-otlp-http-egress`
- Pending a person: after Argo CD syncs, check that `kubectl -n devops get networkpolicy devops-default-perimeter -o yaml` names only port 4318 in the egress to `otel`.
