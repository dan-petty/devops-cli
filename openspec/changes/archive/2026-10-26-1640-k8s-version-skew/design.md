# Design: Kubernetes Version Skew Verification

## Context
See `proposal.md` for motivation and system constraints.

## Goals / Non-Goals

**Goals:**
- Include `server_version` in `Snapshot` via `VersionApi.get_code`.
- Add `get_code` to `plan_doctor_requests` so `--dry-run` shows the call.
- Provide pure helper functions to parse versions and determine skew according to Kubernetes skew policy.
- Emit warning findings in `devops k8s doctor` for kubectl skew (> 1 minor) and kubelet skew (> 3 minors older or newer).
- Emit a console warning in `devops k8s deploy-stack` when kubectl skew is detected, without aborting execution.
- Document skew policy and homelab status in `k8s/README.md`.

**Non-Goals:**
- Upgrading k3s or kubelet binaries in the homelab cluster (tracked in dan-petty/homelab#3).
- Downgrading or pinning older `kubectl` versions in `tools.lock`.
- Halting or aborting `deploy-stack` execution on version skew.

## Decisions

### Decision 1: Version parsing with `packaging.version.Version`
- **Choice**: Use `packaging.version.Version` to parse Kubernetes semantic versions including build metadata (e.g. `v1.31.4+k3s1`).
- **Alternative Considered**: Custom regex parsing.
- **Evidence / Rationale**: Regex parsing is brittle and fails on complex build tags or pre-release metadata. `packaging` is an existing dependency and handles PEP 440 versions reliably.

### Decision 2: Cache `server_version` in `KubernetesService`
- **Choice**: In `KubernetesService.is_cluster_reachable()`, retain `git_version` from `VersionApi.get_code()` in cache and expose `server_version(context)` method.
- **Alternative Considered**: Spawning `kubectl version -o json` or making redundant API calls.
- **Evidence / Rationale**: `is_cluster_reachable()` already probes `VersionApi.get_code()` during reachability checks. Capturing this result incurs zero additional network overhead.

### Decision 3: Pure version-skew diagnostic functions
- **Choice**: Implement `check_kubectl_version_skew(server_ver, kubectl_ver)` and `diagnose_version_skew(snapshot, kubectl_ver)` as pure helper functions that accept version strings or snapshots and return findings or formatted warnings.
- **Alternative Considered**: Direct inline logic within CLI commands.
- **Evidence / Rationale**: Pure functions enable complete unit test coverage with fake data without needing active cluster connections or monkeypatching subprocesses.

## Risks / Trade-offs

- **[Risk] Unconventional or unparseable version string returned by custom Kubernetes builds.**
  → *Mitigation*: Wrap version parsing in error handling; if parsing fails, omit the skew finding rather than raising an unhandled exception.
- **[Risk] Minor discrepancy in kubectl vs server releases during upgrade transitions.**
  → *Mitigation*: Emit findings and logs as `warning` severity rather than `critical`, ensuring workflows are alerted without being blocked.
