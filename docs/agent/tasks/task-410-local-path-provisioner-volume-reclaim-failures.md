# Task 410: Local-Path Provisioner Volume Reclaim Failures

**Issue**: [#410](https://github.com/dan-petty/devops-cli/issues/410)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

`VolumeFailedDelete` with `create process timeout after 120 seconds` leaves the helper pod `Terminating` indefinitely — three days, in the observed case — and the `PersistentVolume` is never reclaimed. Storage leaks silently and the only evidence is an event nobody is watching.

#### Key Deliverables:
- Context & Rationale*: `VolumeFailedDelete` with `create process timeout after 120 seconds` leaves the helper pod `Terminating` indefinitely — three days, in the observed case — and the `PersistentVolume` is never reclaimed. Storage leaks silently and the only evidence is an event nobody is watching.
- Constraint*: Reclamation deletes data. Any automated remediation must confirm the volume is genuinely orphaned rather than merely slow to detach, so the first deliverable is detection and reporting, not deletion.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
