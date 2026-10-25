# k8s-bootstrap Specification

## Purpose
The automated bootstrapping of local Minikube Kubernetes clusters with the Calico container network interface to enforce network security policies.

## Requirements

### Requirement: Minikube cluster starts with Calico CNI
When `devops k8s bootstrap` or internal cluster runtime starts a Minikube cluster, it SHALL include `--cni=calico` in the `minikube start` command arguments.

#### Scenario: Minikube starts with GPU support
- **WHEN** GPU hardware is present and Minikube starts
- **THEN** the command arguments include `minikube`, `start`, `--driver=docker`, `--cni=calico`, and `--gpus=all`

#### Scenario: Minikube starts without GPU support
- **WHEN** GPU hardware is not present and Minikube starts
- **THEN** the command arguments include `minikube`, `start`, `--driver=docker`, and `--cni=calico`

### Requirement: Bootstrap command help reflects Calico CNI
The `devops k8s bootstrap` command help documentation SHALL describe that Minikube is bootstrapped with Calico.

#### Scenario: CLI help display
- **WHEN** a user requests help for `devops k8s bootstrap`
- **THEN** the command description specifies Calico

### Requirement: Devcontainer bootstrap-k8s prints deploy command
When `devops devcontainer bootstrap-k8s` completes Minikube cluster startup, it SHALL print the command to deploy the Kubernetes stack with the target stack and Minikube context, and SHALL NOT auto-deploy any Kubernetes stack.

#### Scenario: Bootstrap prints deploy-stack command
- **WHEN** `devops devcontainer bootstrap-k8s --stack infra` completes
- **THEN** it prints `devops k8s deploy-stack --stack infra --context minikube`
