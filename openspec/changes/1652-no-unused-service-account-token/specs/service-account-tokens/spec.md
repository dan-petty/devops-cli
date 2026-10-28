## Purpose

Which pods of the cluster mount a Kubernetes API token: only a pod that calls the API, through a role bound to its ServiceAccount, or a pod that a named exception explains.

## ADDED Requirements

### Requirement: A pod that does not call the Kubernetes API mounts no ServiceAccount token
Each pod that a manifest under `k8s/` declares, and each pod that a chart of an Argo CD Application makes with its values file, SHALL mount no ServiceAccount token, unless a Role or ClusterRole binds its ServiceAccount. A pod turns the token off with `automountServiceAccountToken: false` on the pod, or on its ServiceAccount when the pod does not set the field. A pod in `CONST_K8S_SERVICE_ACCOUNT_TOKEN_EXCEPTIONS` SHALL be the only other pod with a token, and each exception SHALL have a reason.

#### Scenario: A manifest pod mounts a token
- **WHEN** a test reads each workload under `k8s/`, with the ServiceAccounts, RoleBindings and ClusterRoleBindings under `k8s/`
- **THEN** each workload that is not an exception sets the field to `false`, or names a ServiceAccount that sets it to `false`, or names a ServiceAccount that a binding under `k8s/` names

#### Scenario: A chart pod mounts a token
- **WHEN** a test reads the values file of each chart that an Application installs, with the token value of each pod of that chart and the role that the chart binds to it
- **THEN** each pod that mounts a token and is not an exception has a role

#### Scenario: An Application installs a chart that the test does not know
- **WHEN** an Application installs a chart that has no entry in the test's table of chart pods
- **THEN** the test fails and names the chart

#### Scenario: An exception is stale
- **WHEN** an exception names a pod that the test does not find, or a pod that mounts no token, or a pod with a role
- **THEN** the test fails and names the exception

#### Scenario: The pod field wins over the ServiceAccount field
- **WHEN** the check reads a pod that sets the field to `true` and names a ServiceAccount that sets it to `false`
- **THEN** the check reports that the pod mounts a token
