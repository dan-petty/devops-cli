# Task 204: Remediate DevSecOps Review Findings & Enhance Self-Improvement Loop

**Issue**: [#204](https://github.com/dan-petty/devops-cli/issues/204)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.18`
**Priority**: `priority/p1-high`
**Scope**: `scope/security`

---

## 1. Description & Architectural Objectives

Remediate 11 verified security, path containment, and secret masking findings from review session `20260913-231617`, disarm 2 recurrent false-positive hallucination patterns in `common_hallucinations.json`, and enhance the self-improvement feedback loop and review prompts.

### Key Deliverables
1. **Path Containment & Traversal Hardening**:
   - Enforce `SqlitePlanStore` database path containment within project directories / temp test locations.
   - Validate `DEVOPS_CLI_CONFIG` environment variable against path traversal and forbidden system paths.
   - Validate `run_subprocess` `cwd` parameter against traversal and forbidden system paths.
   - Validate devcontainer volume mount targets against path traversal.
2. **SSRF & Network Egress Hardening**:
   - Enforce private RFC 1918 IP rejection in Jaeger trace querying (`query_jaeger_trace`) while preserving local loopback.
3. **Secret Masking & Sensitive Data Exposure Prevention**:
   - Mask secrets in `SandboxLogLine.content`, `SandboxExecResult.stdout`, `SandboxExecResult.stderr`, and `PanicIncident` paths.
   - Mask secrets in `_render_threads_table` first comment summaries.
   - Mask and cap exception details in `_sync_configured_k8s_context` warning messages.
   - Mask secrets in `_start_minikube_cluster` status messages.
4. **K8s Autostart & Configuration Hygiene**:
   - Integrate `should_autostart_minikube()` in `switch_context`.
   - Validate `KUBECONFIG` if set in the environment before executing `kubectl` or `minikube` commands.
5. **Native DevOps CLI GitHub Rate Management & Pacing**:
   - Implement `src/devops_cli/github/rate_limiter.py` providing token-bucket pacing, quota threshold safety guards, adaptive exponential backoff with jitter on secondary rate limits, and an in-memory TTL cache for idempotent reads.
   - Implement centralized `run_gh()` runner routing all GitHub CLI interactions through the rate manager.
   - Implement `devops gh api` native rate-budgeted command and enhance `devops gh rate-limit` with throttling telemetry.
   - Enforce strict prohibition of bare `gh` CLI commands across `AGENTS.md` and agent instructions.
6. **Self-Improvement Memory & Anti-Hallucination Calibration**:
   - Register `HALLUCINATION-NONEXISTENT-FIXER-PAYLOAD` and `HALLUCINATION-CI-ALLOW-BLOCKED-STATE` in `common_hallucinations.json`.
   - Update `src/devops_cli/ai/tasks/review.md` and `docs/SELF_IMPROVEMENT.md`.
   - Run `devops review export-feedback` to sync `.data/agent/feedback_dataset.jsonl`.

---

## 2. Verification & Acceptance Criteria

- [x] All 11 verified findings from session `20260913-231617` remediated.
- [x] GitHub rate limiter, `run_gh()` runner, and `devops gh api` implemented and unit tested.
- [x] All corresponding unit tests authored in canonical submodule test files pass 100%.
- [x] Architectural invariants satisfied (cyclomatic complexity $\le 10$, nesting depth $\le 5$).
- [x] All 10 `devops ci` quality gates pass cleanly.
- [x] `feedback_dataset.jsonl` updated via `devops review export-feedback`.
