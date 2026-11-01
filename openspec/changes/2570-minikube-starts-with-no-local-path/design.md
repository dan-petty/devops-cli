# Design

## Decisions

- **Pass `--addons=storage-provisioner-rancher` on `minikube start`.** It is atomic with the start, it leaves no moment in which the cluster runs without the class, and it follows the flag `--cni=calico` that #990 added to the same function. `minikube start --dry-run` accepts the flag (see Feasibility in `proposal.md`).
- **Keep the flags of the start in one module tuple of `cluster_runtime.py`.** The GPU call, the CPU call and the texts (dry run and the two success texts) read the tuple, with `--gpus=all` added for the GPU call. The two calls and the texts then cannot differ. The tuple has one owner, so it stays in the module (CONTRIBUTING.md, constants).
- **Name the flag in the dry-run text, the success texts and the two manual-start hints.** The dry run is the would-be command, and a hint that omits the flag starts the cluster with the defect.
- **Use the rancher `local-path` class, not `standard`.** Nine manifest files name `local-path`, the homelab runs the same provisioner, and the volume-placement rules (`tests/core/test_k8s_local_path_placement.py`) assume its semantics.

## Rejected alternatives

- **`minikube addons enable storage-provisioner-rancher` after the start.** It is a second command to keep, and a failure between the two leaves a cluster without the class. The flag on the start has neither problem.
- **Change every claim to the class `standard`.** It needs a change in nine manifest files and breaks parity with the homelab, which runs the class `local-path` (`k8s/README.md`, Prerequisites).
- **Enable the addon on a running cluster too.** `_start_minikube` runs only when minikube is not running (`_run_k8s_bootstrap_worker` in `src/devops_cli/commands/devcontainer.py`, `bootstrap` in `src/devops_cli/commands/k8s/bootstrap.py`, `switch_context` in `src/devops_cli/commands/k8s/cluster_context.py`). A run of `minikube addons enable` on every call adds a request that the issue does not ask for. The README names the one-time command for a cluster that already runs.
