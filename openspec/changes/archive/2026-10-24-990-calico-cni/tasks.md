# Tasks

Selection: We pick Calico because local sandbox egress policies (#702) and namespace perimeters (#913) require NetworkPolicy enforcement, which minikube's default CNI does not provide.

## 1. Minikube startup passes calico CNI and command help matches

- [x] 1.1 Write failing offline tests in `tests/test_k8s_bootstrap.py` asserting `minikube start` includes `--cni=calico` and that bootstrap help text documents Calico, and verify failure on merge-base with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Update `_start_minikube` in `src/devops_cli/commands/k8s/cluster_runtime.py`, register `HELP.k8s.bootstrap` in `src/devops_cli/commands/k8s/__init__.py`, update `bootstrap` docstring in `src/devops_cli/commands/k8s/bootstrap.py`, and update messages in `src/devops_cli/lang/en/messages.py`
- [x] 1.3 Update existing tests in `tests/test_k8s_bootstrap.py` and `tests/test_devcontainer.py` to match the updated Minikube argv and messages, and verify with `uv run devops ci test tests/test_k8s_bootstrap.py tests/test_devcontainer.py`
- [x] 1.4 Regenerate CLI documentation with `uv run devops docs generate --sync-readme` and verify with `uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
