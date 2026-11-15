# Proposal: #5793

## Why

The Security Scan reports KSV-0121 at HIGH for the GPU feature discovery DaemonSet, and issue #5793 asks for the judgment that SECURITY.md names. The container mounts `/sys` from the host for GPU device and bus discovery, so the manifest change is deferred to #5646 and the alert needs a dated ignore entry.

## What Changes

- Add one `misconfigurations` entry to `.trivyignore.yaml` for the rule `KSV-0121` on the path `k8s/gpu-feature-discovery/daemonset.yaml`.
- Give the entry a `statement` that names the sysfs host path mount of GFD v0.16.2 and the tracking issue #5646.
- Set `expired_at` to the day of the commit plus 3 days, the agent limit of SECURITY.md.
- Add `test_the_repository_ignore_file_holds_the_sysfs_mount_entry` to `tests/security/test_trivy_config_ignore.py`; it finds the entry among the entries of the file and asserts its rule, its path, its statement and its expiry date.
- Keep the GPU feature discovery DaemonSet out of the diff, because #5646 delivers the manifest change.
- Add a requirement to `trivy-config-alerts` for the dated entry, because the ignore file changes what the Security Scan reports.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `trivy-config-alerts`: The sysfs mount of the GPU workload holds a dated ignore entry

## Impact

- Code: `.trivyignore.yaml`
- Tests: `tests/security/test_trivy_config_ignore.py`

## Feasibility

- The premise of the issue is that Trivy reports KSV-0121 for `k8s/gpu-feature-discovery/daemonset.yaml`. Running `trivy config k8s/gpu-feature-discovery/daemonset.yaml` reports KSV-0121 (HIGH): daemonset gpu-feature-discovery in default namespace shouldn't have volumes set to {"/sys"}.
- The path `SECURITY.md` defines the judgment process under "Judging a Trivy-config Alert": an agent judges an alert of severity HIGH within 14 days by fixing the file or adding a dated entry to `.trivyignore.yaml` with rule id, paths, statement and expired_at within 3 days.
- Removing `/sys` from `k8s/gpu-feature-discovery/daemonset.yaml` breaks GPU discovery in GFD v0.16.2. Tracking issue #5646 tracks the non-privileged and safe device access for GFD.
- The path `.trivyignore.yaml` exists in the repository.
- `TrivyConfigScanner` in `src/devops_cli/security/trivy.py` automatically passes `--ignorefile .trivyignore.yaml`.
- The new test joins `tests/security/test_trivy_config_ignore.py`.

## Existing Tool Considered

Trivy's `.trivyignore.yaml` ignore file covers the need: Trivy config is the pinned, maintained scanner, `TrivyConfigScanner` names that file with `--ignorefile`, and an entry takes the rule, the paths, a statement and an expiry date, so the change adopts it and builds no code.

## Dependencies

None.
