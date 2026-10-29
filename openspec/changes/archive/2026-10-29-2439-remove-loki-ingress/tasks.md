# Tasks

## 1. Failing Invariant Tests

- [x] 1.1 Add `test_no_ingress_routes_to_loki_in_the_logging_namespace` and `test_no_ingress_is_in_the_logging_namespace` to `tests/invariants/test_k8s_manifests.py`, and verify both fail while `loki-ingress` is present. `uv run pytest tests/invariants/test_k8s_manifests.py -k "loki or logging_namespace"`

## 2. Delete the Dead Ingress

- [x] 2.1 Delete Ingress `loki-ingress` from `k8s/ingress/ingress-routes.yaml`.
- [x] 2.2 Verify the two invariant tests pass and the manifest still loads. `uv run pytest tests/invariants/test_k8s_manifests.py`

## 3. Quality Gate

- [x] 3.1 Record the failing-then-passing evidence. `uv run devops ci fail-to-pass --base origin/main`
- [x] 3.2 Confirm the static checks and test suites pass. `uv run devops ci`
- [x] 3.3 Archive the OpenSpec change. `uv run devops openspec archive 2439-remove-loki-ingress`
