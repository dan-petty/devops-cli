# homelab-project-destinations Specification

## Purpose
Enforces Argo CD AppProject destination boundaries for the homelab project so base cluster infrastructure can deploy cleanly.

## Requirements

### Requirement: Homelab AppProject destination namespaces
AppProject `homelab` SHALL admit `mattermost-operator` and `cnpg-system` in its destination namespaces list, alongside `mattermost`.

#### Scenario: Homelab AppProject permits operator and system namespaces
- **WHEN** a test inspects `k8s/argocd/apps/projects.yaml`
- **THEN** AppProject `homelab` destinations include `namespace: mattermost-operator` and `namespace: cnpg-system`

### Requirement: The homelab AppProjects admit both repositories
The AppProjects `homelab` and `homelab-system` in `k8s/argocd/apps/projects.yaml` SHALL list both `https://github.com/dan-petty/homelab` and `https://github.com/dan-petty/devops-cli` in `sourceRepos`.

#### Scenario: The source repositories of the two projects
- **WHEN** a person runs `kubectl -n argocd get applications` after Argo CD syncs Application `cluster`
- **THEN** no Application of project `homelab` or `homelab-system` has the condition `InvalidSpecError`, and each Application that reads either repository is `Synced`

### Requirement: Project homelab reports no orphan for the homelab repository credential
AppProject `homelab` SHALL hold the entry `{group: '', kind: Secret, name: repo-homelab}` in `orphanedResources.ignore`, because the owner makes that repository credential Secret in namespace `argocd` and no Application tracks it.

#### Scenario: The credential Secret exists
- **WHEN** Secret `repo-homelab` exists in namespace `argocd`, and a person runs `kubectl -n argocd get applications -o jsonpath='{..conditions[*].type}'`
- **THEN** no Application of project `homelab` has the condition `OrphanedResourceWarning` for Secret `repo-homelab`

### Requirement: Project homelab reports no orphan for the CloudNativePG monitoring ConfigMap
AppProject `homelab` SHALL hold the entry `{group: '', kind: ConfigMap, name: cnpg-default-monitoring}` in `orphanedResources.ignore`, because the CloudNativePG operator writes that ConfigMap into each namespace that has a Cluster, with no `ownerReferences` and no tracking id, so no Application tracks it.

#### Scenario: The ignore entry of the AppProject
- **WHEN** a test inspects `k8s/argocd/apps/projects.yaml`
- **THEN** AppProject `homelab` `orphanedResources.ignore` holds the entry `{group: '', kind: ConfigMap, name: cnpg-default-monitoring}`

### Requirement: Project homelab keeps its orphan warning and the default CloudNativePG queries
AppProject `homelab` SHALL keep `orphanedResources.warn` set to `true`, so Argo CD still reports other orphans. The Clusters SHALL NOT set `disableDefaultQueries`, so the default monitoring queries stay active and the `cnpg_collector_up` metric keeps its samples.

#### Scenario: The orphan warning and the default queries
- **WHEN** a test inspects `k8s/argocd/apps/projects.yaml` and `k8s/llm/gateway-db.yaml`
- **THEN** AppProject `homelab` `orphanedResources.warn` is `true`, and the gateway database Cluster holds no `disableDefaultQueries` field

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
