## ADDED Requirements

### Requirement: deploy-stack installs each chart at the version that its Application pins
Each Helm release that `devops k8s deploy-stack` installs SHALL name a chart and a version that an Argo CD Application under `k8s/argocd/apps/` pins, so a cluster without Argo CD runs the same chart releases as the homelab.

#### Scenario: A chart update moves only the Application pin
- **WHEN** a test reads each release of `deploy-stack` and the chart sources of the Applications under `k8s/argocd/apps/`
- **THEN** each release's chart name and version are the `chart` and `targetRevision` of an Application source
