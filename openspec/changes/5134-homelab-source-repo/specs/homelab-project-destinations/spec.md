## ADDED Requirements

### Requirement: Homelab AppProjects admit the homelab repository
The AppProjects `homelab` and `homelab-system` in `k8s/argocd/apps/projects.yaml` SHALL list both `https://github.com/dan-petty/homelab` and `https://github.com/dan-petty/devops-cli` in `sourceRepos`.

#### Scenario: A test reads the source repositories of the two projects
- **WHEN** a test reads `k8s/argocd/apps/projects.yaml`
- **THEN** the `sourceRepos` of `homelab` hold the homelab repository and the devops-cli repository
- **AND** the `sourceRepos` of `homelab-system` hold the homelab repository and the devops-cli repository

### Requirement: Project homelab ignores the homelab repository credential
AppProject `homelab` SHALL hold the entry `{group: '', kind: Secret, name: repo-homelab}` in `orphanedResources.ignore`, because the owner makes that repository credential Secret in namespace `argocd` and no Application tracks it.

#### Scenario: A test reads the orphan ignore list of project homelab
- **WHEN** a test reads AppProject `homelab` in `k8s/argocd/apps/projects.yaml`
- **THEN** `orphanedResources.ignore` holds the entry with group `''`, kind `Secret` and name `repo-homelab`
