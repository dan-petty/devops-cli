## ADDED Requirements

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
