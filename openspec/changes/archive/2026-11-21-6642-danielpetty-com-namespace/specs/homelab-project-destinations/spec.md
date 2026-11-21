## ADDED Requirements

### Requirement: Project homelab reports no orphan for the site repository credential
AppProject `homelab` SHALL hold the entry `{group: '', kind: Secret, name: repo-danielpetty-com}` in `orphanedResources.ignore`, because the owner makes that repository credential Secret in namespace `argocd` and no Application tracks it.

#### Scenario: The site credential Secret exists
- **WHEN** Secret `repo-danielpetty-com` exists in namespace `argocd`, and a person runs `kubectl -n argocd get applications -o jsonpath='{..conditions[*].type}'`
- **THEN** no Application of project `homelab` has the condition `OrphanedResourceWarning` for Secret `repo-danielpetty-com`
