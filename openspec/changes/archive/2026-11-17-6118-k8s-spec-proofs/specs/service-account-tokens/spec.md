## REMOVED Requirements

### Requirement: A pod that does not call the Kubernetes API mounts no ServiceAccount token
**Reason**: Its scenarios named a test that reads each workload and each chart values file, with a table of the pods of each chart. That test asserts values of manifests, and #6082 deletes it. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "A pod with no role mounts no ServiceAccount token" holds the same rule, and names its one exception.

## ADDED Requirements

### Requirement: A pod with no role mounts no ServiceAccount token
Each pod that a manifest under `k8s/` declares, or that a chart of an Argo CD Application makes with its values file, SHALL mount no ServiceAccount token, unless a Role or ClusterRole binds its ServiceAccount. The Qdrant pod of namespace `llm` SHALL be the only exception, because the Qdrant chart has no value that turns its token off (qdrant/qdrant-helm#506).

#### Scenario: A pod mounts a token that no role needs
- **WHEN** a person lists the pods that have a projected `serviceAccountToken` volume source with `kubectl get pods --all-namespaces -o json`, and the ServiceAccounts that a binding names with `kubectl get rolebindings,clusterrolebindings --all-namespaces -o json`
- **THEN** each such pod of the tree has a ServiceAccount that a binding names, or is the Qdrant pod of namespace `llm`
