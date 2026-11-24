## ADDED Requirements

### Requirement: The k8s-monitoring values map the pod annotation to the repo stream label
The k8s-monitoring values MUST map the pod annotation `roadmap.devops-cli/repository` to the Loki stream label `repo` under `podLogsViaLoki`, so each line of a unit pod carries the stream label `repo` with the casefolded repository of its work.

#### Scenario: The values hold the mapping and the chart renders it
- **WHEN** I run `uv run devops ci --check --only charts` over `k8s/monitoring/k8s-monitoring-values.yaml` on a host that has helm and docker
- **THEN** the values file holds `annotations: {roadmap.devops-cli/repository: repo}` under `podLogsViaLoki`, and the render of the chart maps that annotation to the label `repo` in the pod-logs configuration of the collector `alloy-logs`

### Requirement: The router pod keeps its stream labels
The router Deployment `roadmap-service` MUST carry no `roadmap.devops-cli/repository` annotation on its pod template, so the router pod gets no `repo` stream label and its one pod keeps one stream set.

#### Scenario: The rendered router Deployment carries no repository annotation
- **WHEN** I run `uv run devops ci --check --only k8s` over the manifests of `k8s/devops/roadmap-service/`
- **THEN** the row passes, and the rendered Deployment `roadmap-service` in namespace `devops` carries no `roadmap.devops-cli/repository` annotation on its pod template
