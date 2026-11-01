# Tasks

## 1. Add storage-provisioner-rancher addon to minikube start

Reads: none. Changes: `src/devops_cli/commands/k8s/cluster_runtime.py`, `tests/test_k8s_cluster_runtime.py`.

- [ ] 1.1 Write a test in tests/test_k8s_cluster_runtime.py that mocks subprocess.run, calls _start_minikube, and asserts the arguments list passed to minikube start includes --addons=storage-provisioner-rancher alongside --driver=docker and --cni=calico, and verify that `uv run devops ci test tests/test_k8s_cluster_runtime.py` fails on the base
- [ ] 1.2 In _start_minikube in src/devops_cli/commands/k8s/cluster_runtime.py, add the string --addons=storage-provisioner-rancher to the list of arguments passed to the minikube start subprocess call, next to the existing --driver=docker and --cni=calico flags, and verify that `uv run devops ci test tests/test_k8s_cluster_runtime.py` passes
- [ ] 1.3 Update k8s/README.md Prerequisites: replace the sentence that says devops devcontainer does not enable the addon and the manual minikube addons enable instruction with a statement that devops devcontainer post-start enables the storage-provisioner-rancher addon automatically, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
