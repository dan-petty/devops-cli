# service-account-tokens Specification

## Purpose
Which pods of the cluster mount a Kubernetes API token. A pod has a token only when a role binds its ServiceAccount, or when a named exception explains it.

## Requirements

### Requirement: A pod that does not call the Kubernetes API mounts no ServiceAccount token
This requirement applies to each pod that a manifest under `k8s/` declares. It also applies to each pod that a chart of an Argo CD Application makes with its values file. Such a pod SHALL mount no ServiceAccount token, unless a Role or ClusterRole binds its ServiceAccount. A pod in the test's table of exceptions SHALL be the only other pod with a token. Each exception SHALL have a reason.

#### Scenario: A manifest pod mounts a token
- **WHEN** a test reads each workload under `k8s/`, with the ServiceAccounts and the bindings under `k8s/`
- **THEN** each workload that is not an exception has its token off, or a binding under `k8s/` names its ServiceAccount

#### Scenario: A chart pod mounts a token
- **WHEN** a test reads the values file of each chart that an Application installs, with the test's table of the pods of that chart
- **THEN** each pod with a token that is not an exception has a role

#### Scenario: An Application installs a chart that the test does not know
- **WHEN** an Application installs a chart that the test's table of chart pods does not name, or a version that the entry does not name
- **THEN** the test fails and names the chart and the version

#### Scenario: Argo CD or Kustomize changes a pod that the test reads from its file
- **WHEN** an Application source has an option that changes objects, such as inline chart values, or a kustomization under `k8s/` patches a checked object
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
- **WHEN** the check reads a pod that sets the field to `false` and has a volume that holds a token
- **THEN** the check reports that the pod mounts a token
