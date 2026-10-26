# Proposal: Kubernetes Version Skew Verification

## Why
devops-cli pins `kubectl` at version 1.37.1 in `tools.lock`, while the target homelab cluster runs Kubernetes 1.31 (`v1.31.4+k3s1`), leaving client and server six minor versions apart (#1640). Upstream Kubernetes supports `kubectl` only within one minor version of the API server and kubelets within three minor versions, yet `devops k8s doctor` and `devops k8s deploy-stack` execute without warning about this skew.

## What Changes
- Add `server_version` to `Snapshot` in `src/devops_cli/k8s/doctor.py`, populated via `VersionApi.get_code` during snapshot collection.
- Register `get_code` in `plan_doctor_requests` so `devops k8s doctor --dry-run` reports the planned call.
- Add pure helper functions to parse versions using `packaging.version.Version` and evaluate skew for both `kubectl` and node kubelets.
- Add a `version-skew` diagnostic rule to `devops k8s doctor` that warns if `kubectl` minor skew exceeds 1 or if any node kubelet is older than the API server by more than 3 minor versions.
- Emit a warning in `devops k8s deploy-stack` before applying manifests or Helm releases when `kubectl` version skew is detected, without aborting execution.
- Update `k8s/README.md` Prerequisites to document the version skew policy, current `tools.lock` pin, and homelab status.

This change fits in one pull request.

## Capabilities

### New Capabilities
- `k8s-doctor`: Cluster diagnosis, node and workload rule evaluation, request planning, and version-skew reporting.

### Modified Capabilities
- `k8s-helm-deploy`: Add kubectl version skew detection and warning to stack deployment workflow before applying resources.

## Impact
- Affected code: `src/devops_cli/k8s/doctor.py`, `src/devops_cli/k8s/service.py`, `src/devops_cli/commands/k8s/diagnostics.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/config/constants.py`, `k8s/README.md`.
- No breaking API changes or dependency changes; `packaging` is already a project dependency.

## Feasibility
- Upstream Kubernetes version skew documentation confirms `kubectl` is supported within $\pm 1$ minor version of `kube-apiserver`, and kubelet is supported up to 3 minor versions older and no newer than `kube-apiserver`.
- `packaging.version.Version` successfully parses semantic versions and build tags such as `v1.31.4+k3s1` and `1.37.1`.
- `VersionApi.get_code()` in the official Kubernetes Python client returns `VersionInfo` with attribute `git_version`.
- `devops_cli.tools_lock.load_tools_lock().binary["kubectl"].version` returns the pinned `1.37.1` version string.

## Existing Tool Considered
We evaluated using `kubectl version --client -o json` as an external subprocess. Spawning a subprocess adds unnecessary latency and requires a functioning `kubectl` binary on the host PATH. We instead utilize the in-process `VersionApi.get_code` call already performed by `KubernetesService` and parse versions with standard `packaging.version.Version`.
