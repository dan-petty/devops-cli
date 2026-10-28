## Purpose

Which pods of the cluster mount a Kubernetes API token: only a pod that calls the API, through a role bound to its ServiceAccount, or a pod that a named exception explains.

## ADDED Requirements

### Requirement: A pod that does not call the Kubernetes API mounts no ServiceAccount token
Each pod that a manifest under `k8s/` declares, and each pod that a chart of an Argo CD Application makes with its values file, SHALL mount no ServiceAccount token, unless a Role or ClusterRole binds its ServiceAccount. A pod in the test's table of exceptions SHALL be the only other pod with a token, and each exception SHALL have a reason.

#### Scenario: A manifest pod mounts a token
- **WHEN** a test reads each workload under `k8s/`, with the ServiceAccounts, RoleBindings and ClusterRoleBindings under `k8s/`
- **THEN** each workload that is not an exception sets the field to `false`, or names a ServiceAccount that sets it to `false`, or names a ServiceAccount that a binding under `k8s/` names

#### Scenario: A chart pod mounts a token
- **WHEN** a test reads the values file of each chart that an Application installs, with the token value of each pod of that chart and the role that the chart binds to it
- **THEN** each pod that mounts a token and is not an exception has a role

#### Scenario: An Application installs a chart that the test does not know
- **WHEN** an Application installs a chart that has no entry in the test's table of chart pods, or pins a chart version other than the version of the entry
- **THEN** the test fails and names the chart and the version

#### Scenario: Argo CD or Kustomize changes a pod that the test reads from its file
- **WHEN** an Application source gives a chart values that are not in its values files, or a path source has options that change objects, or a kustomization under `k8s/` patches a workload, a ServiceAccount, a Secret, a binding or a claim
- **THEN** the test fails and names the option or the patch

#### Scenario: An exception is stale
- **WHEN** an exception names a pod that the test does not find, or a pod that mounts no token, or a pod with a role
- **THEN** the test fails and names the exception

### Requirement: The check finds each token that a pod mounts
The check SHALL read the field `automountServiceAccountToken` of the pod, or of its ServiceAccount when the pod does not set it. It SHALL report a token unless that field is `false`. A pod with a projected `serviceAccountToken` source, or with a volume of a Secret of type `kubernetes.io/service-account-token`, SHALL mount a token, whatever the field says.

#### Scenario: The pod field wins over the ServiceAccount field
- **WHEN** the check reads a pod that sets the field to `true` and names a ServiceAccount that sets it to `false`
- **THEN** the check reports that the pod mounts a token

#### Scenario: A pod mounts a token as a volume
- **WHEN** the check reads a pod that sets the field to `false` and has a projected `serviceAccountToken` source, or a volume of a Secret of type `kubernetes.io/service-account-token`
- **THEN** the check reports that the pod mounts a token
