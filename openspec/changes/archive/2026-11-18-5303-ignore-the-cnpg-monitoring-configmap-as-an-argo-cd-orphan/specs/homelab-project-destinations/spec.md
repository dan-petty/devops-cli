## ADDED Requirements

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
