## ADDED Requirements

### Requirement: minikube start enables local-path storage
The _start_minikube function SHALL pass --addons=storage-provisioner-rancher to the minikube start command, so the cluster has a StorageClass named local-path from the first start.

#### Scenario: Start command includes the addon flag
- **WHEN** _start_minikube constructs the argument list for the minikube start subprocess call
- **THEN** the argument list includes the string --addons=storage-provisioner-rancher
