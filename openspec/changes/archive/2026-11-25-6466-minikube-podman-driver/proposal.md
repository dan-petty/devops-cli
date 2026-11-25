# Proposal: #6466

## Why
In the devcontainer image from #6414, `docker` is `podman-docker` (rootless by default) while the rootful Podman API service listens at `/var/run/docker.sock` (`-> /run/podman/podman.sock`). Devcontainer Minikube bootstrap starts `minikube` with `--driver=docker` without explicitly setting `DOCKER_HOST=unix:///var/run/docker.sock`, leaving login shells vulnerable to `/etc/profile.d/podman-docker.sh` and lacking an offline test or Topology 1 documentation of the socket.

## What Changes
- Export `DEFAULT_MINIKUBE_DOCKER_HOST` (`unix:///var/run/docker.sock`) and `minikube_docker_env()` in `src/devops_cli/commands/k8s/cluster_runtime.py`, pass `env` through `_minikube_running` / `_start_minikube`, and pass `DOCKER_HOST=unix:///var/run/docker.sock` in devcontainer Kubernetes bootstrap (`src/devops_cli/commands/devcontainer.py`).
- Update `docs/DEVCONTAINER_USAGE.md` Topology 1 to name `--driver=docker` and the rootful Podman socket `/var/run/docker.sock` (retaining `#6466` links with no `#MINIKUBE_ISSUE` placeholder).
- Add offline unit test coverage in `tests/commands/test_devcontainer.py` (`minikube_driver`), `tests/commands/k8s/test_k8s_bootstrap.py`, and doc assertions in `tests/docs/test_docs.py` (`devcontainer_usage_driver`, `minikube_issue_link`).

## Capabilities

### Modified Capabilities
- `k8s-bootstrap`: Require devcontainer bootstrap and runtime Minikube calls to use `--driver=docker` with `DOCKER_HOST=unix:///var/run/docker.sock`, plus guide documentation.

## Impact
Affects `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/commands/k8s/cluster_runtime.py`, `docs/DEVCONTAINER_USAGE.md`, `tests/commands/test_devcontainer.py`, `tests/commands/k8s/test_k8s_bootstrap.py`, and `tests/docs/test_docs.py`. Live Minikube start in the devcontainer on the owner's rootless Podman host and on Docker remains the manual merge gate.

## Feasibility
Confirmed against `origin/main`: `CONST_DOCKER_DEFAULT_UNIX_SOCKET` and `CONST_PODMAN_ROOTFUL_SOCKET_PATH` exist in `src/devops_cli/config/constants.py`; `/var/run/docker.sock -> /run/podman/podman.sock` and `minikube` exist in the devcontainer; `docs/DEVCONTAINER_USAGE.md` already replaced `#MINIKUBE_ISSUE` with `#6466` and still omits `/var/run/docker.sock` in Topology 1.

## Existing Tool Considered
Minikube is the existing tool for local cluster startup (`Alternatives check of 2026-11-20: not-applicable`). No new dependency is added.
