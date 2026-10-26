# Spec Delta

## ADDED Requirements

### Requirement: Post-Helm custom resource CRD verification
The system SHALL check whether the cluster serves the kind of each post-Helm manifest file before executing deletion or deployment. When a cluster does not serve a post-Helm custom resource kind, `teardown-stack` SHALL skip deletion of that manifest and print a warning message. When a cluster does not serve a post-Helm custom resource kind during `deploy-stack`, the system SHALL skip applying that manifest and print a warning message.

#### Scenario: Teardown skips post-Helm manifest when CRD is not served
- **WHEN** `devops k8s teardown-stack` executes and the cluster `api-resources` does not include the manifest's kind
- **THEN** the system does not execute `kubectl delete` for that manifest, prints a warning naming the skipped manifest and unserved kind, and continues stack teardown

#### Scenario: Teardown deletes post-Helm manifest when CRD is served
- **WHEN** `devops k8s teardown-stack` executes and the cluster `api-resources` includes the manifest's kind
- **THEN** the system executes `kubectl delete -f <file> --ignore-not-found` for that manifest

#### Scenario: Deploy reports post-Helm manifest apply failure when CRD is not served
- **WHEN** `devops k8s deploy-stack` executes and the cluster `api-resources` does not include the manifest's kind
- **THEN** the system does not execute `kubectl apply` for that manifest, prints a warning naming the manifest and unserved kind, and continues stack deployment
