# k8s-api-connection Specification

## Purpose
How devops-cli connects to the Kubernetes API: the configuration that a connection uses, chosen by one rule, and what a context switch changes in the process and on disk.

## Requirements

### Requirement: One configuration rule for each connection
A connection to the Kubernetes API SHALL use the kubeconfig when the kubeconfig names the resolved context, and the pod's service account only when it does not. Each connection SHALL hold its own client configuration and SHALL NOT change the client's global default configuration.

#### Scenario: The kubeconfig names the context
- **WHEN** the kubeconfig names the resolved context and the process also has a service account
- **THEN** the connection uses the server of that kubeconfig context

#### Scenario: The kubeconfig does not name the context
- **WHEN** the kubeconfig does not name the resolved context and the process has a service account
- **THEN** the connection uses the server and the token of the service account

#### Scenario: No kubeconfig context and no service account
- **WHEN** the kubeconfig does not name the resolved context and the process has no service account
- **THEN** the connection fails, and the service reports the cluster as not reachable

#### Scenario: The global default is not changed
- **WHEN** a connection is made
- **THEN** the client's global default configuration is the same as before

### Requirement: A context switch leaves the kubeconfig unchanged
Switching the in-process Kubernetes clients to a context SHALL check that the kubeconfig names the context and SHALL point the clients at it, and SHALL NOT write the kubeconfig.

#### Scenario: Switch to a known context
- **WHEN** the in-process clients switch to a context that the kubeconfig names
- **THEN** the next API call goes to the server of that context, and the kubeconfig file is byte for byte the same

#### Scenario: Switch to an unknown context
- **WHEN** the in-process clients switch to a context that the kubeconfig does not name
- **THEN** the switch fails with an error that names the context
