# Design

## Decisions
- Remove `k8s/devops/renovate/` manifests and drop the 4 paths from `PRODUCT_MANIFESTS_BY_STACK["devops"]`. Application devops prunes them on sync.
- Keep the `devops/renovate` Secret row in `cluster_secrets.py` and the `renovate.*` settings. The homelab init container runs `devops gh app-token --app renovate` on the product image and needs them.
- Delete `tests/gate/k8s_checks/renovate.py`, `src/devops_cli/k8s/renovate_token.py`, `tests/support/renovate.py`, and `tests/k8s/test_renovate_token.py`.
- Move the secret row test from `tests/invariants/test_k8s_renovate.py` to `tests/k8s/test_cluster_secrets.py` and delete `tests/invariants/test_k8s_renovate.py`.
- Update `tests/gate/k8s_checks/devops_runtime.py` and `tests/gate/k8s_checks/telemetry_resource.py` to reflect the removed containers.
- Update `docs/TESTING.md` and `docs/CLUSTER.md`.
- Use an OpenSpec spec delta with REMOVED entries for workload requirements in `specs/renovate-service/spec.md`.

## Rejected alternatives
- Move Secret row and settings to homelab: Rejected because the product image runs the token command, and `devops k8s push-secrets` writes the Secret.
- Delete the whole invariant test without moving the row test: Rejected because the row is source code that stays, and source code must have test coverage.
- Edit living spec by hand: Rejected because only openspec archive writes living specs.
