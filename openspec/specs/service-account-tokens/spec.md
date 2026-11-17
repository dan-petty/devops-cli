# service-account-tokens Specification

## Purpose
Which pods of the cluster mount a Kubernetes API token. A pod has a token only when a role binds its ServiceAccount, or when a named exception explains it.

## Requirements

### Requirement: A pod with no role mounts no ServiceAccount token
Each pod that a manifest under `k8s/` declares, or that a chart of an Argo CD Application makes with its values file, SHALL mount no ServiceAccount token, unless a Role or ClusterRole binds its ServiceAccount. The Qdrant pod of namespace `llm` SHALL be the only exception, because the Qdrant chart has no value that turns its token off (qdrant/qdrant-helm#506).

#### Scenario: A pod mounts a token that no role needs
- **WHEN** a person lists the pods that have a projected `serviceAccountToken` volume source with `kubectl get pods --all-namespaces -o json`, and the ServiceAccounts that a binding names with `kubectl get rolebindings,clusterrolebindings --all-namespaces -o json`
- **THEN** each such pod of the tree has a ServiceAccount that a binding names, or is the Qdrant pod of namespace `llm`
