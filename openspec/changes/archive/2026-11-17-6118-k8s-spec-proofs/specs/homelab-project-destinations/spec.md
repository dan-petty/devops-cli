## REMOVED Requirements

### Requirement: Homelab AppProjects admit the homelab repository
**Reason**: Its scenario named a test that reads `k8s/argocd/apps/projects.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "The homelab AppProjects admit both repositories" holds the same rule.

### Requirement: Project homelab ignores the homelab repository credential
**Reason**: Its scenario named a test that reads `k8s/argocd/apps/projects.yaml`. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "Project homelab reports no orphan for the homelab repository credential" holds the same rule.

## ADDED Requirements

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
