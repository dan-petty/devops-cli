# Task 121: Centralized Logging Perimeter Hardening & Fluent Bit Namespace Scoping

**Issue**: [#121](https://github.com/dan-petty/devops-cli/issues/121)
**Status**: Done
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Architectural Objectives

Remediate DevSecOps review findings across the centralized Kubernetes logging manifests (`k8s/logging/`). Harden network perimeters and reduce unconstrained log ingestion by:
1. Binding the Fluent Bit HTTP metrics/health server strictly to `127.0.0.1:2020` instead of `0.0.0.0:2020` to prevent unauthenticated network exposure.
2. Restricting Loki ingress rules in `k8s/logging/networkpolicy.yaml` strictly to authorized consumers: `monitoring` (Grafana) and `logging` (Fluent Bit), eliminating unconstrained ingress paths.
3. Scoping container log collection in Fluent Bit strictly to target application namespaces (`default`, `llm`, `sandbox`) instead of unconstrained globbing across all namespaces.
4. Validating manifests against admission and security policies with `devops k8s validate-policy`.

---

## 2. Planned Changes

1. **`k8s/logging/fluent-bit-values.yaml`**:
   - Update `config.service` to set `HTTP_Listen 127.0.0.1`.
   - Update `config.inputs` to scope `Path` to `/var/log/containers/*_default_*.log, /var/log/containers/*_llm_*.log, /var/log/containers/*_sandbox_*.log`.
2. **`k8s/logging/networkpolicy.yaml`**:
   - Audit and tighten Loki ingress rules to allow access strictly from `monitoring` (Grafana) and intra-namespace `logging` (Fluent Bit).
3. **`tests/test_k8s_logging_security.py`**:
   - Add unit tests verifying `fluent-bit-values.yaml` and `networkpolicy.yaml` compliance against security invariants.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#121) with `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-121-logging-perimeter-hardening.md`.
- [x] Create dedicated topic branch `fix/121-logging-perimeter-hardening`.
- Not checked when merged: update `k8s/logging/fluent-bit-values.yaml` with loopback binding and namespace scoping.
- Not checked when merged: update `k8s/logging/networkpolicy.yaml` to restrict ingress to `monitoring` and `logging`.
- Not checked when merged: author unit tests in `tests/test_k8s_logging_security.py`.
- Not checked when merged: validate manifests with `devops k8s validate-policy`.
- Not checked when merged: run full test suite and CI quality gate.
