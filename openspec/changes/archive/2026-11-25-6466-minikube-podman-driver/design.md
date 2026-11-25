# Design

## Decisions
- **Docker host environment helper in `cluster_runtime.py`**: Define `DEFAULT_MINIKUBE_DOCKER_HOST = f"unix://{CONST_DOCKER_DEFAULT_UNIX_SOCKET}"` (`unix:///var/run/docker.sock`) and `minikube_docker_env()`, reusing existing socket constants in `src/devops_cli/config/constants.py`.
- **Devcontainer bootstrap sets `DOCKER_HOST` unconditionally**: `_run_k8s_bootstrap_worker` and `_start_minikube_cluster` in `src/devops_cli/commands/devcontainer.py` pass `env=runtime.minikube_docker_env()` to `minikube status`, `_start_minikube`, and `minikube update-context`.
- **Shared runtime Podman detection**: When `cluster_runtime._start_minikube` or `_minikube_running` is called without an explicit `env` (for example from `devops k8s switch-context minikube`), `_minikube_env()` sets `DOCKER_HOST=DEFAULT_MINIKUBE_DOCKER_HOST` only when `CONST_PODMAN_ROOTFUL_SOCKET_PATH` exists and `DOCKER_HOST` is unset or differs, preserving custom Docker hosts on non-Podman workstations.
- **Documentation & tests**: Update `docs/DEVCONTAINER_USAGE.md` Topology 1 to document `--driver=docker` and `/var/run/docker.sock`, and add offline tests (`minikube_driver`, `devcontainer_usage_driver`, `minikube_issue_link`).

## Rejected alternatives
- **Switch Minikube to `--driver=podman`**: Rejected because the devcontainer already provides a Docker-compatible rootful Podman API socket at `/var/run/docker.sock` and `--driver=docker` is the shared cross-platform path.
- **Hardcode `DOCKER_HOST=/var/run/docker.sock` on non-Podman workstations without checking**: Rejected because custom host `DOCKER_HOST` settings (for example Docker Desktop or remote sockets) must remain intact outside Podman devcontainers.
- **Live-only test without mocked subprocess check**: Rejected because CI and hermetic test runs forbid starting real `minikube`.
