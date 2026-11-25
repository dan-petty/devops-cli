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

### Requirement: Docker daemon poll uses the clock seam
`_wait_for_docker_daemon` SHALL measure elapsed time with `clock.monotonic()` and wait with `clock.sleep(2)` from `devops_cli.core.clock`, and SHALL keep its default timeout of 45 seconds.

#### Scenario: Unreachable Docker engine
- **WHEN** the Docker engine is unreachable and the poll runs with the default timeout under the fake clock
- **THEN** the function returns False and the clock records 23 waits of 2 seconds

### Requirement: Minikube driver and socket
The devcontainer bootstrap SHALL start Minikube with the `docker` driver and set `DOCKER_HOST=unix:///var/run/docker.sock` when `k8s.context` is `minikube`.

#### Scenario: Bootstrap uses the rootful Podman socket
- **WHEN** `uv run pytest tests/commands/test_devcontainer.py -k minikube_driver` runs with a mocked subprocess
- **THEN** the test passes and asserts the Minikube command has `--driver=docker` and the environment has `DOCKER_HOST=unix:///var/run/docker.sock`

### Requirement: Devcontainer guide names the driver
`docs/DEVCONTAINER_USAGE.md` SHALL name the `docker` driver and the rootful Podman socket in Topology 1.

#### Scenario: Guide names the driver and socket
- **WHEN** `uv run pytest tests/docs/test_docs.py -k devcontainer_usage_driver` runs
- **THEN** the test passes and asserts the Topology 1 section has `--driver=docker` and `/var/run/docker.sock`

### Requirement: Issue link replacement
Each `#MINIKUBE_ISSUE` placeholder in `docs/DEVCONTAINER_USAGE.md` SHALL point to issue #6466.

#### Scenario: Placeholder links resolve to the issue
- **WHEN** `uv run pytest tests/docs/test_docs.py -k minikube_issue_link` runs
- **THEN** the test passes and asserts the file has no `#MINIKUBE_ISSUE` text and has `#6466`

### Requirement: Live Minikube start
In the devcontainer, `devops k8s switch-context minikube` MUST start a Minikube cluster that `kubectl get nodes` shows Ready.

#### Scenario: Live devcontainer check
- **WHEN** a person runs `devops k8s switch-context minikube` in the devcontainer on the owner's rootless Podman host and on Docker
- **THEN** `kubectl get nodes` shows the Minikube node with status `Ready`
