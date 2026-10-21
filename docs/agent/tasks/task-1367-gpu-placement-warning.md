# Task: deploy-stack Warns About GPU Nodes No Ollama Tier Accepts, and the README Documents GPU Placement (#1367)

**Issue**: [#1367](https://github.com/dan-petty/devops-cli/issues/1367)
**Scope**: scope/k8s
**Feasibility**: Read from `k8s/llm/profiles/ollama-profiles.yaml` at release/v0.2.38: nine `llm.devops.io/provider: ollama` DaemonSets each require `nvidia.com/gpu.total-vram-gib` with `In`, and three (`ollama-24gib`, `ollama-48gib`, `ollama-48gib-slow`) also `nvidia.com/gpu.architecture`. A test reads every expression's operator from the file and finds only `In`. `deploy-stack` read nodes only in step 8, after the Argo CD early return, through `_get_unready_nodes`, which returned `[]` on every failure, so no warning placed there could print on an Argo CD-managed cluster and a failed read could not be told from an empty one. The gateway's ConfigMap names Services `ollama-16gib-fast`, `ollama-48gib-fast`, `ollama-48gib-slow` and `ollama-64gib-standard`, and all four exist in `k8s/llm/profiles/services.yaml`. The ServiceMonitor half of this item was delivered by #1794 (Part 8 of `task-1128-monitoring-stack-k8s-monitoring-and-chart-features.md`), so this pull request carries the GPU placement half and closes the item.

## Description

- [x] `deploy-stack --stack llm` reads the nodes once, right after the reachability check and before the Argo CD early return, through `runtime._read_nodes`, which returns `None` when the read fails. `_get_unready_nodes` takes its items from the same reader.
- [x] `src/devops_cli/k8s/gpu_placement.py` reads each tier's required label values from `ollama-profiles.yaml`, never repeating them in code. An expression whose operator is not `In` raises `KubernetesDeployError`, and a test pins that every profile holds only `In`. The label keys and the GPU predicate's keys are in `config/constants.py` (`CONST_K8S_GPU_*`, `CONST_K8S_OLLAMA_*`), and the warning text is in `MESSAGES.k8s`.
- [x] A GPU node is one with `nvidia.com/gpu` capacity above zero or `nvidia.com/gpu.present=true`. It warns about each one no tier accepts, naming the node and its label:
  - a missing `total-vram-gib`, with `kubectl label node <node> nvidia.com/gpu.total-vram-gib=<N>Gi`;
  - a value no tier lists, with that value;
  - an `architecture` outside those of the tiers that accept its total, with the accepted ones.

  When no node satisfies any tier, it also says no Ollama pod will schedule. When the read fails, it says it could not check the labels. The deploy goes on and exits 0 in every case.
- [x] `tests/test_k8s_gpu_placement.py` runs `deploy-stack --stack llm` over a cluster that answers `kubectl get nodes -o json`:
  - a labelled node, an unlabelled one, a value outside every tier, a node without GPUs, an architecture mismatch, no node matching any tier, and a failed read;
  - one case on the Argo CD-managed path, one that the infra stack reads no node for this, and one that `--dry-run` makes no `_run_cmd`, `subprocess.run` or `Popen` call.

  Six of them fail with the check switched off.
- [x] The GPU placement section of `k8s/README.md` gives the tier table with each tier's accepted `total-vram-gib` and `architecture` values, what sets the labels and the `kubectl label node` command, the warning, the gateway's alias Services, and what `llm-gateway-perimeter` admits.
- [x] The 36 commented-out `gpu.architecture` and `gpu.family` lines in six DaemonSets are removed. #1042's three live `gpu.architecture` selectors stay, and `rg -n '^\s*#.*(gpu\.(family|architecture)|operator:|values:)' k8s/llm/profiles/ollama-profiles.yaml` and `rg -n 'gpu\.family' k8s/llm k8s/README.md` print nothing.
- The node-provisioning automation sets `total-vram-gib` only on multi-GPU nodes and rounds it to the nearest whole GiB. It lives outside this repository, and the README records that behaviour for whoever changes it.
- Pending a person: after the next deploy, `devops k8s deploy-stack --stack llm` warns only about GPU nodes that `kubectl get nodes -L nvidia.com/gpu.total-vram-gib,nvidia.com/gpu.architecture` shows no tier accepts.
