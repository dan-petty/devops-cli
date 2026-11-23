# Design

## Decisions

### Document the runbook in k8s/README.md
`k8s/README.md` holds cluster decisions and operational procedures for Kubernetes storage and StatefulSets.
Placing the migration runbook there keeps operational steps together.

### Order of operations
1. Patch bound PersistentVolumes to `Retain` first.
2. Delete StatefulSets with `--cascade=orphan`.
This order prevents accidental volume deletion by the provisioner if a claim is detached.

### Automated verification test
A new test in `tests/k8s/test_k8s_retain_migration_docs.py` validates that the section exists, contains the exact commands, and maintains the safe execution order.

## Rejected alternatives

- **Build a new CLI command**: The migration is a one-time procedure for 8 bound volumes. A runbook avoids adding permanent maintenance code.
- **Run the migration in CI**: CI has no live cluster access and cannot execute data-bearing operations.
- **Delete StatefulSet before patching PersistentVolumes**: Deleting StatefulSets first risks data loss if a claim with `Delete` policy is detached.
