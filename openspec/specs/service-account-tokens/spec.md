# service-account-tokens Specification

## Purpose
Which pods of the product base `k8s/devops` mount a Kubernetes API token. A pod has a token only when a role binds its ServiceAccount.

## Requirements

### Requirement: A pod with no role mounts no ServiceAccount token
Each pod that a manifest of `k8s/devops/` declares SHALL mount no ServiceAccount token, unless a Role or ClusterRole binds its ServiceAccount.

#### Scenario: A pod mounts a token that no role needs
- **WHEN** a person lists the pods that have a projected `serviceAccountToken` volume source with `kubectl get pods --all-namespaces -o json`, and the ServiceAccounts that a binding names with `kubectl get rolebindings,clusterrolebindings --all-namespaces -o json`
- **THEN** each such pod of `k8s/devops/` has a ServiceAccount that a binding names
