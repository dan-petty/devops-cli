# k8s-stateful-storage Specification

## Purpose
How the stateful manifests of the repository use the StorageClass `local-path-retain` for new volumes, how Argo CD ignores the immutable class of a bound claim, and the checks that enforce them.

## Requirements

### Requirement: Stateful manifests request the Retain class
Each PersistentVolumeClaim, claim template, including the Alloy CR template, and CloudNativePG `Cluster` storage block under `k8s/` that names a storage class MUST name `local-path-retain`.

#### Scenario: The k8s row finds no local-path claim
- **WHEN** A person runs `uv run devops ci --check --only k8s`.
- **THEN** The row passes and its `check_every_claim_names_the_retain_class` check reports no rendered claim or claim template on `local-path`.

### Requirement: Argo CD ignores the class of a bound claim
Each Argo CD Application whose rendered objects include a PersistentVolumeClaim or a StatefulSet with a claim template MUST list the storage class field under `spec.ignoreDifferences` and set `RespectIgnoreDifferences=true` in `spec.syncPolicy.syncOptions`.

#### Scenario: A sync leaves the immutable field alone
- **WHEN** A person runs `uv run devops ci --check --only k8s`.
- **THEN** The row passes and its `check_each_claim_application_ignores_the_storage_class` check names the `ignoreDifferences` entry and the `RespectIgnoreDifferences` option of each such Application.

### Requirement: The docs name the Retain class and the patch step
`k8s/README.md` and `docs/SERVICE_PATTERNS.md` SHALL name `local-path-retain` as the class for a new stateful workload, and `k8s/README.md` SHALL give the `kubectl patch pv` command for a bound volume.

#### Scenario: The storage docs test finds the class and the patch command
- **WHEN** A person runs `uv run devops ci test tests/invariants/test_k8s_storage_docs.py`.
- **THEN** The test passes and asserts `local-path-retain` in both documents and the `kubectl patch pv` command in `k8s/README.md`.

### Requirement: The gate rejects the old class
The `k8s` row MUST fail when a rendered claim or claim template under `k8s/` names `local-path`.

#### Scenario: The new check fails on the old class
- **WHEN** A person changes one `storageClassName` back to `local-path` and runs `uv run devops ci --check --only k8s`.
- **THEN** The row fails and the `check_every_claim_names_the_retain_class` check names the claim or claim template and `local-path`.
