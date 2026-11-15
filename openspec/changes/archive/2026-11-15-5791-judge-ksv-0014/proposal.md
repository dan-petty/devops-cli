# Proposal: #5791

## Why

The Security Scan reports KSV-0014 at HIGH for `k8s/gpu-feature-discovery/daemonset.yaml`, and issue #5791 asks for the judgment that SECURITY.md names. The container sets `privileged: true` but lacks `readOnlyRootFilesystem: true`. SECURITY.md specifies that fixing the manifest file is the first choice. Setting `readOnlyRootFilesystem: true` protects the container while keeping privileged GPU discovery intact.

## What Changes

- Set `readOnlyRootFilesystem: true` in the container `securityContext` of `k8s/gpu-feature-discovery/daemonset.yaml`.
- Keep `privileged: true` and the two hostPath mounts (`output-dir` and `host-sys`) needed for GPU device and sysfs discovery.
- Add offline manifest tests in `tests/invariants/test_k8s_gpu_feature_discovery.py` that assert `readOnlyRootFilesystem: true` and the required privileged settings.
- Add the requirement to `trivy-config-alerts` for the read-only root file system on `gpu-feature-discovery`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `trivy-config-alerts`: The GPU feature discovery workload sets a read-only root file system

## Impact

- Code: `k8s/gpu-feature-discovery/daemonset.yaml`
- Tests: `tests/invariants/test_k8s_gpu_feature_discovery.py`

## Feasibility

- Running `trivy config k8s/gpu-feature-discovery/daemonset.yaml` reports KSV-0014 (HIGH): Container 'gpu-feature-discovery' of DaemonSet 'gpu-feature-discovery' should set 'securityContext.readOnlyRootFilesystem' to true.
- GFD v0.16.2 writes output only to the mounted `/etc/kubernetes/node-feature-discovery/features.d` path and reads `/sys`, requiring no writable root filesystem.
- Setting `readOnlyRootFilesystem: true` satisfies KSV-0014 without breaking GFD runtime behavior.
- The change does not require any `.trivyignore.yaml` entry.

## Existing Tool Considered

Trivy config covers the need: it runs in CI and reports KSV-0014. The change fixes the file directly instead of adding an ignore entry, fulfilling SECURITY.md guidance.

## Dependencies

None.
