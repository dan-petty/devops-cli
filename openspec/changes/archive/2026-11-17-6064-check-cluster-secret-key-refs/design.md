# Design

## Decisions
- Add `check_secret_key_refs` in `src/devops_cli/k8s/cluster_secrets.py`: takes a directory path and the generator table `table: Iterable[ClusterSecret] = CLUSTER_SECRETS`, scanning YAML manifests and Helm values files under `k8s/` for `secretKeyRef` blocks.
- Secret scoping: Resolve the namespace from `metadata.namespace` or the top-level subfolder under `k8s/`. Match Secret reference against `table` rows. If the Secret name is not in the table, skip it (allowing operator/chart-generated secrets like `llm-gateway-db-app`). If the Secret is in the table, verify the key exists in the Secret's entries; if not, record a finding naming the file, the secret ref, and the missing key.
- Live check documentation: In `k8s/README.md` Cluster Secrets section, state that before merging a manifest reading a Secret, run `devops k8s push-secrets --only <namespace>/<name> --plan` and verify the output shows `unchanged`.

## Rejected alternatives
- Generic manifest linter (kube-linter/conftest): Cannot inspect the internal Python generator table.
- Cluster-side admission webhook (Kyverno/Gatekeeper): Only acts at admission time after Secret is already missing and pod fails.
- Hardcoded copy of generator table in test: Drifts when secrets are added or modified; importing `CLUSTER_SECRETS` directly guarantees a single source of truth.
