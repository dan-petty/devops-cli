# Spec Delta

## ADDED Requirements

### Requirement: Devcontainer bootstrap-k8s prints deploy command
When `devops devcontainer bootstrap-k8s` completes Minikube cluster startup, it SHALL print the command to deploy the Kubernetes stack with the target stack and Minikube context, and SHALL NOT auto-deploy any Kubernetes stack.

#### Scenario: Bootstrap prints deploy-stack command
- **WHEN** `devops devcontainer bootstrap-k8s --stack infra` completes
- **THEN** it prints `devops k8s deploy-stack --stack infra --context minikube`
