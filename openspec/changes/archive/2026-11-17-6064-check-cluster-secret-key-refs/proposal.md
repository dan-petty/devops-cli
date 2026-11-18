# Proposal: #6064

## Why
Pod `llm/qdrant-0` stopped in `CreateContainerConfigError` because Secret `llm/qdrant-api-key` held no key `read-only-api-key`. Pull request #5725 merged the manifest that reads the key before a person pushed the key. This change adds a check that fails when a `secretKeyRef` names a key that the generator table of `devops k8s push-secrets` has no row for, and documents the live `--plan` check that must show `unchanged` before the merge. Closes #6064.

## What Changes
- Add `check_secret_key_refs` to `src/devops_cli/k8s/cluster_secrets.py` to validate that each `secretKeyRef` under `k8s/` that refers to a Secret in the generator table references a known key of that Secret.
- Add test `tests/k8s/test_cluster_secret_key_refs.py` covering unknown keys, known keys, skipped chart Secrets, and documentation requirements.
- Add gate check in `tests/gate/k8s_checks/cluster_secrets.py` for CI gate enforcement.
- Update `k8s/README.md` Cluster Secrets section to document the live `devops k8s push-secrets --only <namespace>/<name> --plan` check and `unchanged` requirement before merge.

## Capabilities
- `cluster-secret-keys`: validation of `secretKeyRef` references against the cluster secrets generator table.

## Impact
Prevents pull requests from merging manifests that read ungenerated or unpushed secret keys, preventing `CreateContainerConfigError` regressions in cluster workloads.

## Feasibility
Confirmed against `k8s/llm/values-qdrant.yaml`, `src/devops_cli/k8s/cluster_secrets.py`, and existing `secretKeyRef` usages across `k8s/`.

## Existing Tool Considered
kube-linter and conftest check manifest shape only and have no knowledge of the push-secrets generator table rows. Custom repository test with zero external dependency.
