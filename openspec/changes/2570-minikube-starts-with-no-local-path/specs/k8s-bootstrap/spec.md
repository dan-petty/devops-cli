## ADDED Requirements

### Requirement: Minikube cluster starts with local-path storage
When `devops k8s bootstrap`, `devops devcontainer bootstrap-k8s` or the internal cluster runtime starts a Minikube cluster, it SHALL include `--addons=storage-provisioner-rancher` in the `minikube start` command arguments, so that the cluster has the StorageClass `local-path` that the claims of the stacks name. The hints that tell a person to start Minikube by hand SHALL name the same flag.

#### Scenario: Minikube starts with GPU support and the addon
- **WHEN** GPU hardware is present and Minikube starts
- **THEN** the command arguments include `minikube`, `start`, `--driver=docker`, `--cni=calico`, `--addons=storage-provisioner-rancher` and `--gpus=all`

#### Scenario: Minikube starts without GPU support and with the addon
- **WHEN** GPU hardware is not present and Minikube starts
- **THEN** the command arguments include `minikube`, `start`, `--driver=docker`, `--cni=calico` and `--addons=storage-provisioner-rancher`

#### Scenario: The CPU fallback keeps the addon
- **WHEN** the start with GPU support fails and Minikube starts again without it
- **THEN** the command arguments of the second start include `--addons=storage-provisioner-rancher`

#### Scenario: The dry run names the addon
- **WHEN** the start is a dry run
- **THEN** the result text names `--addons=storage-provisioner-rancher` and no `minikube` process starts

#### Scenario: The hints name the addon
- **WHEN** a command tells a person to start Minikube by hand
- **THEN** the hint names `--addons=storage-provisioner-rancher`
