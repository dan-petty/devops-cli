## MODIFIED Requirements

### Requirement: The app-of-apps applies the homelab Applications server-side
The Applications `devops`, `ingress` and `mattermost` in `k8s/argocd/apps/` SHALL have `ServerSideApply=true` in their `argocd.argoproj.io/sync-options` annotation, and no other Application SHALL have it. The Application `cluster` SHALL have the annotation `argocd.argoproj.io/client-side-apply-migration-manager` with the value `argocd-controller`.

#### Scenario: A test reads the Application manifests
- **WHEN** a test reads `k8s/argocd/bootstrap/bootstrap.yaml`, `k8s/argocd/bootstrap/cluster.yaml` and each Application in `k8s/argocd/apps/`
- **THEN** the Applications with `ServerSideApply=true` in their sync-options annotation are `devops`, `ingress` and `mattermost` and no other
- **AND** `cluster` names `argocd-controller` as its client-side apply migration manager
