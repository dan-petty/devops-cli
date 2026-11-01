# Tasks

## 1. Minikube starts with the addon that gives the class local-path

Reads: `src/devops_cli/commands/k8s/cluster_runtime.py`, `tests/commands/k8s/test_k8s_bootstrap.py`, lines 270 to 340 of `tests/commands/test_devcontainer.py`, lines 588 to 598 of `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/commands/k8s/cluster_runtime.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/k8s/test_k8s_bootstrap.py`, `tests/commands/test_devcontainer.py`.

- [ ] 1.1 Write the failing tests first. In `tests/commands/k8s/test_k8s_bootstrap.py`, change the expected argv of `test_start_minikube_with_gpu`, `test_start_minikube_gpu_fallback_to_cpu` and `test_start_minikube_cpu_only` to `--driver=docker --cni=calico --addons=storage-provisioner-rancher` (and `--gpus=all` last on the GPU call). Change the five expected texts of the success and dry-run tests, and the two lines of the module docstring, to name the flag after `--cni=calico`. Add `test_minikube_start_hints_name_the_local_path_addon`, which asserts that `MESSAGES.k8s.start_minikube_tip` and `MESSAGES.k8s.minikube_not_running` contain `--addons=storage-provisioner-rancher`. In `tests/commands/test_devcontainer.py`, change the expected text of the GPU and CPU `bootstrap-k8s` tests and the CPU argv assert (lines 297, 334 and 335). Keep `test_start_minikube_pins_calico_cni_argv_and_help_text_matches`. Verify that `uv run devops ci test tests/commands/k8s/test_k8s_bootstrap.py tests/commands/test_devcontainer.py` fails on the base, and that each failure is an assertion on the argv, a text or a hint that lacks the flag (not an import or collection error)
- [ ] 1.2 In `_start_minikube` (`src/devops_cli/commands/k8s/cluster_runtime.py`), keep the flags `--driver=docker`, `--cni=calico` and `--addons=storage-provisioner-rancher` in one module tuple. Build both `minikube start` calls (the GPU call with `--gpus=all` added) and the dry-run and success texts from it, so no call or text names the flags alone. Add the flag to `start_minikube_tip` and `minikube_not_running` in `src/devops_cli/lang/en/messages.py`. Write the messages in ASD-STE100. Verify that `uv run devops ci test tests/commands/k8s/test_k8s_bootstrap.py tests/commands/test_devcontainer.py tests/commands/k8s/test_k8s_runtime_cmd.py` passes
- [ ] 1.3 Verify that the tests fail on the base tree and pass on the branch with `uv run devops ci fail-to-pass --base origin/main`, and keep its output for the pull request (rule 4 of AGENTS.md)

## 2. The documents say that devops starts minikube with the addon

Reads: lines 22 to 33 of `k8s/README.md`, lines 400 to 408 of `docs/DEVCONTAINER_USAGE.md`. Changes: `k8s/README.md`, `docs/DEVCONTAINER_USAGE.md`.

This group changes documents only, so it adds no test. Write each sentence in ASD-STE100, on the line of its item, without a line break.

- [ ] 2.1 Verify with `! git grep -n -e "does not enable it" -e "enables no Minikube add-ons" -- k8s/README.md docs/DEVCONTAINER_USAGE.md`, which exits 1 on the base (it finds the two old sentences) and exits 0 when task 2.2 is done
- [ ] 2.2 In `k8s/README.md` (Prerequisites, the minikube bullet of the storage layer), replace the sentences "`devops devcontainer` does not enable it, so without it ..." and the instruction to run `minikube addons enable storage-provisioner-rancher` as the normal step. Say that `devops` starts minikube with `--addons=storage-provisioner-rancher`, so the class `local-path` exists from the first start, and that a minikube which already runs keeps its addons and needs `minikube addons enable storage-provisioner-rancher` once. In `docs/DEVCONTAINER_USAGE.md` (Add-Ons), replace "devops-cli enables no Minikube add-ons; ..." with the same fact: devops-cli enables `storage-provisioner-rancher`, and other addons stay with the person (`minikube addons enable ingress`, `metrics-server`, `dashboard`)
- [ ] 2.3 Verify that `uv run devops ci docs` passes. No command, option or help text changes, so `uv run devops docs generate --sync-readme` has nothing to regenerate

## Workflow follow-up

- Pending a person: on a live minikube, run `devops devcontainer bootstrap-k8s` and then `kubectl get sc local-path`. It must list the class with the provisioner `rancher.io/local-path`. The minikube of the devcontainer is stopped, and a test never reaches a cluster.
- Pending a person: on the same cluster, run `devops k8s deploy-stack --stack infra` and `kubectl get pvc -A`. No claim with `storageClassName: local-path` may stay `Pending` once a pod that mounts it is scheduled (the class binds with `WaitForFirstConsumer`).
