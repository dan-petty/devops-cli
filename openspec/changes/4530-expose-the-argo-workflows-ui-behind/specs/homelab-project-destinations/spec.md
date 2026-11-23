## ADDED Requirements

### Requirement: The homelab-system project admits the argo-workflows namespace
AppProject `homelab-system` in `k8s/argocd/apps/projects.yaml` SHALL list namespace `argo-workflows` among its destinations, so Application `ingress` may render the UI Ingress and its links ConfigMap there.

#### Scenario: The live destinations of the project
- **WHEN** A person runs the live check `kubectl -n argocd get appproject homelab-system -o jsonpath='{.spec.destinations[*].namespace}'` on the cluster that rendered `k8s/argocd/apps/projects.yaml`
- **THEN** The answer names `argo-workflows`, and Application `ingress` reports `Synced`
