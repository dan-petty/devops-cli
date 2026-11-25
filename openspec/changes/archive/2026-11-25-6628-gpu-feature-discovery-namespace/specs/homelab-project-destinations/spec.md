## ADDED Requirements

### Requirement: Namespace entry with the stack labels
`k8s/namespaces.yaml` SHALL define the `gpu-feature-discovery` Namespace with the `app.kubernetes.io/part-of: devops-cli-stack` label, the `privileged` Pod Security labels (`enforce`, `warn`, `audit`), and the `argocd.argoproj.io/sync-options: Prune=false,Delete=false` annotation.

#### Scenario: The k8s check accepts the new namespace
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command exits 0 and reports no error for `k8s/namespaces.yaml`

### Requirement: DaemonSet leaves the default namespace
The `gpu-feature-discovery` DaemonSet (`k8s/gpu-feature-discovery/daemonset.yaml`) SHALL set `metadata.namespace` to `gpu-feature-discovery` and reference `gpu-feature-discovery` in its `ignore-check.kube-linter.io/non-isolated-pod` annotation.

#### Scenario: DaemonSet targets the dedicated namespace
- **WHEN** a test inspects `k8s/gpu-feature-discovery/daemonset.yaml`
- **THEN** `metadata.namespace` is `gpu-feature-discovery` and `non-isolated-pod` references `gpu-feature-discovery` rather than `default`

### Requirement: Application destination names the new namespace
The `gpu-feature-discovery` Application (`k8s/argocd/apps/gpu-feature-discovery.yaml`) SHALL set `spec.destination.namespace` to `gpu-feature-discovery`.

#### Scenario: Argo CD Application targets gpu-feature-discovery
- **WHEN** a test inspects `k8s/argocd/apps/gpu-feature-discovery.yaml`
- **THEN** `spec.destination.namespace` is `gpu-feature-discovery`

### Requirement: AppProject homelab-system admits the new namespace
The `homelab-system` AppProject (`k8s/argocd/apps/projects.yaml`) SHALL list `gpu-feature-discovery` in `spec.destinations` while keeping `default`.

#### Scenario: The project admits the new destination
- **WHEN** a test inspects `k8s/argocd/apps/projects.yaml`
- **THEN** AppProject `homelab-system` `spec.destinations` contains both `gpu-feature-discovery` and `default`
