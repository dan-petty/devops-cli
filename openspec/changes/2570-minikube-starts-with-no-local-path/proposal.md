# Proposal

## Why

Issue #2570: the devcontainer starts minikube with `minikube start --driver=docker --cni=calico` and enables no storage addon. The default `storage-provisioner` addon serves only the class `standard`. No class `local-path` exists, so each claim that names it stays `Pending`. Minikube has the addon `storage-provisioner-rancher`, which adds the class `local-path`. The fix is one flag on the start command.

## What Changes

- `_start_minikube` in `src/devops_cli/commands/k8s/cluster_runtime.py` adds `--addons=storage-provisioner-rancher` to both `minikube start` calls (the GPU call and the CPU call). It keeps the flags of the start in one tuple, so the two calls and the texts that name the flags cannot differ.
- The dry-run text and the two success texts of `_start_minikube` name the new flag, so they stay true. The dry run is the would-be command.
- The two hints that tell a person to start minikube by hand (`start_minikube_tip` and `minikube_not_running` in `src/devops_cli/lang/en/messages.py`) name the new flag. A person who follows a hint without the flag would start the cluster with the defect of the issue.
- The tests that pin the old argv and the old texts change with the code: `tests/commands/k8s/test_k8s_bootstrap.py` and `tests/commands/test_devcontainer.py`.
- `k8s/README.md` (Prerequisites) and `docs/DEVCONTAINER_USAGE.md` (Add-Ons) say that `devops` starts minikube with the addon. Both documents now say the opposite. The start command in the GPU Passthrough block of `docs/DEVCONTAINER_USAGE.md` (line 401) names neither `--cni=calico` nor the addon, so it changes too.
- The change is observable (a `devops` start command and its messages), so it carries a spec delta: one ADDED requirement in `k8s-bootstrap`. The requirement `Minikube cluster starts with Calico CNI` of the base spec stays true and is not modified, because its scenarios say that the arguments "include" the listed flags.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-bootstrap`: an ADDED requirement, minikube starts with the addon that gives the class `local-path`.

## Impact

- Code: `src/devops_cli/commands/k8s/cluster_runtime.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/commands/k8s/test_k8s_bootstrap.py` (the tests of `_start_minikube`, which exist), `tests/commands/test_devcontainer.py` (two tests of `bootstrap-k8s`, which pin the argv and the text).
- Documents: `k8s/README.md`, `docs/DEVCONTAINER_USAGE.md`.
- No command, option or help text changes, so `devops docs generate --sync-readme` has nothing to regenerate.
- A minikube that is already running keeps its addons, because `_start_minikube` runs only when minikube is not running. That cluster needs `minikube addons enable storage-provisioner-rancher` once. The README says so.

## Acceptance

Each criterion of the refined issue maps to a group of `tasks.md`.

- Requirement "local-path StorageClass exists" (after `devops devcontainer post-start`, `kubectl get sc local-path` returns the class): group 1 delivers the cause, the flag on every start. `post-start` starts minikube through `_spawn_background_k8s_bootstrap`, then `bootstrap-k8s`, then `_start_minikube` (`src/devops_cli/commands/devcontainer.py`). The check on a live cluster is pending a person: this devcontainer's minikube is stopped, and a test never reaches a cluster.
- Requirement "PVCs bind" (after `devops k8s deploy-stack --stack infra`, no `local-path` claim stays `Pending`): pending a person, on a live minikube. The class binds with `volumeBindingMode: WaitForFirstConsumer`, so a claim binds when a pod that mounts it is scheduled.
- Requirement "Start command includes addon" (`_start_minikube` passes `--addons=storage-provisioner-rancher`): group 1.
- The text that tells a person about the addon (`k8s/README.md`, `docs/DEVCONTAINER_USAGE.md`): group 2.

## Feasibility

Each item below came from a command run on 2026-11-01 against origin/main (`9f3b7010`) and minikube v1.39.0.

- The start command has no addon flag. `git grep -n -e "--addons" -- src tests .devcontainer` prints nothing (exit 1). `src/devops_cli/commands/k8s/cluster_runtime.py` lines 101 and 108 hold the two start calls, `["minikube", "start", "--driver=docker", "--cni=calico", "--gpus=all"]` and `["minikube", "start", "--driver=docker", "--cni=calico"]`.
- Nothing newer did or removed this. `git log --oneline 9e73e6d0..origin/main -- src/devops_cli/commands/k8s/cluster_runtime.py` prints nothing. `git log -S"storage-provisioner-rancher" origin/main -- src k8s docs` prints only `ac78d39e` (#2571), the commit that wrote the README sentence. An open-issue search for `minikube local-path` returns #2570 and #1082, and #1082 is about Argo CD and Gitea.
- Minikube v1.39.0 lists the addon. `minikube addons list` prints `storage-provisioner-rancher | minikube | disabled | 3rd party (Rancher)`, next to `default-storageclass` and `storage-provisioner`.
- `minikube start` takes the flag. `minikube start --help` prints `--addons=[]: Enable one or more addons, in a comma-separated format.` A dry run with the exact flags succeeds and starts no cluster: `minikube start -p plan2570-dry --dry-run --driver=docker --cni=calico --addons=storage-provisioner-rancher` ends with `dry-run validation complete!`, and `minikube profile list` shows only the profile `minikube` in its table. The dry run leaves a stub profile directory: `minikube profile list` then prints `Found 1 invalid profile(s)`, and `minikube delete -p plan2570-dry` removes it. A repeat of the check can set `MINIKUBE_HOME` to a temporary directory instead.
- The addon gives the class `local-path`. The addon manifest in the minikube repository (file storage-provisioner-rancher.yaml.tmpl in the addon directory, at tag v1.39.0) holds one StorageClass: `name: local-path`, `provisioner: rancher.io/local-path`, `volumeBindingMode: WaitForFirstConsumer`, `reclaimPolicy: Delete`. It has no `is-default-class` annotation, so `standard` stays the default class.
- The claims exist. `git grep -n "storageClass" -- k8s | grep local-path` lists the seven files of the issue (`k8s/devops/roadmap-service/pvc.yaml`, `k8s/gitea/values.yaml`, `k8s/monitoring/grafana-values.yaml`, `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/pyroscope-values.yaml`, `k8s/otel/tempo-values.yaml`). It lists two more, in the `chat` stack: `k8s/mattermost/database.yaml` and `k8s/mattermost/files-pvc.yaml`. The same fix serves them.
- Tests exist that pin the old argv: `tests/commands/k8s/test_k8s_bootstrap.py` (lines 68, 89, 103 and 162 for the argv, and lines 65, 88, 102, 112 and 122 for the texts) and `tests/commands/test_devcontainer.py` (lines 297, 334 and 335).
- Two documents state the old behavior: `k8s/README.md` line 32 and `docs/DEVCONTAINER_USAGE.md` line 406.
- Not checked on a live cluster: the minikube of this devcontainer is stopped, and a start takes minutes and changes the host. The two live checks are in `## Workflow follow-up` of `tasks.md`.

## Existing Tool Considered

The addon `storage-provisioner-rancher` of minikube (a third-party addon of Rancher, listed by `minikube addons list`) gives the class `local-path` with the provisioner that the homelab runs. Nothing is built. The change passes one flag to the tool and deletes no code.
