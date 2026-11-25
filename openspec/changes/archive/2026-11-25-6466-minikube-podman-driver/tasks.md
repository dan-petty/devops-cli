# Tasks

## 1. Behavior

- [x] 1.1 Write failing offline tests for `minikube_driver` in `tests/commands/test_devcontainer.py` and for `devcontainer_usage_driver` and `minikube_issue_link` in `tests/docs/test_docs.py`
  - Verification: `$ uv run pytest -n 0 tests/commands/test_devcontainer.py -k minikube_driver`
- [x] 1.2 Pass `DOCKER_HOST=unix:///var/run/docker.sock` from devcontainer bootstrap and Podman devcontainer runtime into Minikube calls (`src/devops_cli/commands/devcontainer.py`, `src/devops_cli/commands/k8s/cluster_runtime.py`)
  - Verification: `$ uv run pytest -n 0 tests/commands/test_devcontainer.py tests/commands/k8s/test_k8s_bootstrap.py`

## 2. Documents

- [x] 2.1 Update `docs/DEVCONTAINER_USAGE.md` Topology 1 to document `--driver=docker` and the rootful Podman socket `/var/run/docker.sock`
  - Verification: `$ uv run pytest -n 0 tests/docs/test_docs.py -k "devcontainer_usage_driver or minikube_issue_link" && uv run devops docs check`
