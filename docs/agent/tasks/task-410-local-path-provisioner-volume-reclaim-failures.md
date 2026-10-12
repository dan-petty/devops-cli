# Task 410: Local-Path Provisioner Volume Reclaim Failures (`devops k8s volume reclaim`)

**Issue**: [#410](https://github.com/dan-petty/devops-cli/issues/410)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/k8s`, `scope/cli`, `priority/p2-medium`
**Feasibility**: Verified against Kubernetes CoreV1Api, dry-run request planning, and CLI Typer runtime.

---

## 1. Description & Objectives

The local-path provisioner's volume reclaim can fail with a `VolumeFailedDelete` event and a helper pod stuck `Terminating` indefinitely, leaving the `PersistentVolume` unreclaimed and storage leaked silently. #408 shipped detection via `devops k8s doctor`, and this issue adds safe, confirmation-gated volume reclamation that acts only on volumes verified to be genuinely orphaned, with request-free `--dry-run` simulation.

#### Key Deliverables:
- [x] Command `devops k8s volume reclaim <name>` supporting positional PV name, `--dry-run`, `--yes`, and `--patch`.
- [x] Verification before mutation that the volume is genuinely orphaned: phase is `Released` or `Failed`, referenced claim is absent/deleted, and no pod in any namespace mounts it.
- [x] Interactive confirmation prompt required before issuing mutating API calls; refuses non-interactive execution unless `--yes` is specified.
- [x] Request-free `--dry-run` simulation that prints the exact API operation without making network calls.
- [x] Clear reporting on successful reclamation indicating the volume name and action taken (`deleted` or `patched`).
- [x] Unit and integration test coverage with structural tuple equality assertions in `tests/test_k8s_volume_reclaim.py`.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
