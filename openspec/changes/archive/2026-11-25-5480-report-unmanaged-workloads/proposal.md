# Proposal: #5480

## Why
Argo CD reports orphaned resources only inside the destination namespaces of each AppProject. A workload created outside those namespaces stays invisible to `devops k8s doctor` and violates the zero-drift rule.

## What Changes
- Add `BIN_KONMON` (`konmon`) in `src/devops_cli/config/commands.py` and `CONST_K8S_DOCTOR_RULE_ORPHANED_WORKLOAD` (`orphaned-workload`) in `src/devops_cli/config/constants.py`.
- Run `konmon check orphaned -o json` (with `-n <namespace>` and `--context <context>` when supplied) during `devops k8s doctor` snapshot collection in `src/devops_cli/k8s/doctor.py`, and include `konmon check orphaned` in `plan_doctor_requests` for `--dry-run`.
- Filter `konmon` JSON findings to `Deployment`, `StatefulSet`, `DaemonSet`, and `CronJob` workloads mapped to `<Kind>/<namespace>/<name>` findings, dropping non-workload kinds, and report a cluster warning finding naming `konmon` when `konmon` is absent from `PATH`, exits non-zero without valid findings, or writes invalid JSON while continuing all other doctor checks.

## Capabilities
- `k8s-doctor`: Run `konmon check orphaned -o json` in `collect` and `--dry-run`, map unmanaged workload kinds to doctor findings, and report missing or failed `konmon` runs without stopping other checks.

## Impact
- Adds read-only unmanaged workload detection to `devops k8s doctor` and updates doctor snapshot/report fixtures and tests.

## Feasibility
- Confirmed against `guettli/konmon` source (`cmd/check.go`, `cmd/output.go`, `checks/orphaned.ts`, `docs/cli/konmon_check.md`): `konmon check orphaned -o json [-n <ns>] [--context <ctx>]` emits `{"findings": [{"kind", "namespace", "name", "message", ...}]}` and exits `0` when clean or `1` when findings exist.
- Confirmed `devops k8s doctor` snapshot collection runs in `src/devops_cli/k8s/doctor.py` via `collect()` -> `diagnose()`, and `DefaultProcessRunner` returns exit `127` (`Executable 'konmon' not found in PATH`) when absent from `PATH`.

## Existing Tool Considered
- `guettli/konmon` (`https://github.com/guettli/konmon`, Apache-2.0, maintained): owner directed adoption per `AGENTS.md` rule 3. Covers cluster-wide `orphaned` resource detection across Argo CD labels/annotations and system namespace skips; `devops k8s doctor` adds the CLI adapter, four-workload kind filtering, missing/failure findings, and offline PATH executable tests.
