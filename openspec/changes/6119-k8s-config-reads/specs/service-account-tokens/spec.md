## REMOVED Requirements

### Requirement: A pod that does not call the Kubernetes API mounts no ServiceAccount token
**Reason**: Scenarios of this requirement described the test that read the manifests, which #6119 deletes (#6060).
**Migration**: The requirement "A pod mounts a ServiceAccount token only when a role binds its ServiceAccount" holds the rule, with scenarios that name a live check or a validator command.

### Requirement: The check finds each token that a pod mounts
**Reason**: The check was a helper of the test that read the manifests, and #6119 deletes that test (#6060: no test asserts a value of a manifest).
**Migration**: kube-linter (`uv run devops k8s lint`) reports a workload that mounts the token of the default ServiceAccount, and `kubectl get pods -A -o json` shows each token volume.

## ADDED Requirements

### Requirement: A pod mounts a ServiceAccount token only when a role binds its ServiceAccount
This requirement applies to each pod that a manifest under `k8s/` declares. It also applies to each pod that a chart of an Argo CD Application makes with its values file. Such a pod SHALL mount no ServiceAccount token, unless a Role or ClusterRole binds its ServiceAccount. The Qdrant pod SHALL be the only exception, until its chart has a value for the field (qdrant/qdrant-helm#506).

#### Scenario: A manifest pod mounts a token
- **WHEN** `uv run devops k8s lint k8s` runs kube-linter on the manifests
- **THEN** kube-linter reports each workload that mounts the token of the default ServiceAccount

#### Scenario: A chart pod mounts a token
- **WHEN** a person runs `kubectl get pods -A -o json` on the cluster
- **THEN** a `kube-api-access-*` volume is only on the pods whose ServiceAccount a Role or ClusterRole binds, and on the Qdrant pod
