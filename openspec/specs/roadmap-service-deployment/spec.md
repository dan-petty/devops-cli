# roadmap-service-deployment Specification

## Purpose
How the roadmap Service and the cluster Jobs run in namespace `devops`: the replica count of `deployment/roadmap-service`, and the model retry count of ConfigMap `devops-cli-config`, which both read.

## Requirements

### Requirement: The Service runs as one pod
`deployment/roadmap-service` SHALL set `replicas: 1` and the `Recreate` strategy, so one pod of the Service runs at a time.

#### Scenario: The manifest is read
- **WHEN** `k8s/devops/roadmap-service/deployment.yaml` is read
- **THEN** its `spec.replicas` is 1 and its `spec.strategy.type` is `Recreate`

### Requirement: A model call in the cluster is sent at most two times
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `ai.max_retries` to 1, and the ConfigMap that a deploy renders from it SHALL keep that value.

#### Scenario: A deploy renders the ConfigMap from the repository's template
- **WHEN** the active config sets `service.repos` and the App's settings, and the ConfigMap is rendered from `k8s/devops/configmap.example.yaml`
- **THEN** the rendered config validates as settings with `ai.model` `devops-background` and `ai.max_retries` 1
