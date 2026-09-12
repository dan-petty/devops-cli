# Task 176: Remediate DevSecOps Review Findings & Enhance Review Self-Improvement Loop

**Issue**: [#176](https://github.com/dan-petty/devops-cli/issues/176)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/review`

---

## 1. Description & Architectural Objectives

Remediate verified security findings from review session `20260912-054338` (including critical path traversal, DNS rebinding SSRF, unbounded timeouts/buffers, secret exposure), and enhance prompts, documentation, and tooling to strengthen the feedback, review, and self-improvement loop.

### Key Objectives
1. **Critical & High Security Findings Remediation**:
   - Validate and contain `DEVOPS_CLI_DATA_DIR` in `src/devops_cli/ui/data_providers.py` and `src/devops_cli/ai/controller/manager.py` against path traversal.
   - Enforce DNS resolution and IP address checking in `web_fetch_tool` (`src/devops_cli/ai/common_tools.py`) to prevent DNS rebinding SSRF.
   - Restrict `SqlitePlanStore` `db_path` in `src/devops_cli/ai/harness/planning.py` to safe project directories.
   - Fix timeout construction in `new_http_client` and `new_async_http_client` in `src/devops_cli/http/client.py`.
   - Ensure `mask_secrets` on payloads in `StepPersistence.save_step` (`src/devops_cli/ai/agents/persistence.py`).
   - Sanitize and bound URLs in `SSRFBlockedError` details (`src/devops_cli/exceptions/security.py`).
   - Bound sleep latency in fault injection (`src/devops_cli/ai/chaos/injector.py`).
   - Bound max input size for JSON repair in `src/devops_cli/ai/response_repair.py`.
   - Remove/sanitize `file://` reference in `src/devops_cli/ai/knowledge_base/devops_cli/libraries/cryptography.md`.
2. **Review & Self-Improvement Loop Enhancement**:
   - Update reviewer prompts in `src/devops_cli/ai/review/` to emphasize automated verification and prevent false positives / detect regressions early.
   - Update documentation (`docs/SELF_IMPROVEMENT.md`, `AGENTS.md`) describing the feedback, review, and self-improvement loop.
3. **Comprehensive Testing & Quality Gates**:
   - Add unit and regression tests for all remediated vulnerabilities and tools.
   - Maintain cyclomatic complexity $\le 10$ and nesting depth $\le 5$ project-wide.
   - Achieve 100% passing across all 10 `devops ci` quality gates with coverage $\ge 90\%$.

---

## 2. Implementation Checklist

- [x] Ground issue [#176](https://github.com/dan-petty/devops-cli/issues/176) in GitHub Projects tracking
- [x] Author dedicated task tracking file `docs/agent/tasks/task-176-review-findings-self-improvement.md`
- [ ] Update `docs/agent/task.md` index
- [ ] Create draft PR for remote branch tracking
- [ ] Remediate critical and high security findings across codebase
- [ ] Update review prompts, persona system instructions, and verification engine
- [ ] Update review and self-improvement documentation
- [ ] Author comprehensive regression tests
- [ ] Validate with targeted `pytest` and full `devops ci` suite
