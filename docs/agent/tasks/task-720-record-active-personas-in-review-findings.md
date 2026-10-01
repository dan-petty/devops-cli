# Task 720: Record Active Personas Accurately in Review Session Findings and Candidates

**Issue**: [#720](https://github.com/dan-petty/devops-cli/issues/720)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `scope/review`, `type/bug`, `priority/p2-medium`

---

## 1. Description & Objectives

When executing `devops ai review` (or `devops review path/branch/pr`) with `--persona <persona>` (such as `--persona devsecops`), the review orchestrator successfully executes only the designated persona and produces findings strictly attributed to that persona. However, `generate_consolidated_report` in `ReviewPipelineOrchestrator` hardcoded `personas=["devsecops", "architect", "qa"]` when serializing `findings.json` and omitted `personas` in `candidates.json` (leaving it as empty `[]`).

This task updates `ReviewPipelineOrchestrator` and `runner.py` to accurately record the active personas evaluated during the session across both `findings.json` and `candidates.json`.

### Key Deliverables Completed:
- [x] **Orchestrator Persona Tracking**:
  - Initialized `self.personas: list[str] = []` on `ReviewPipelineOrchestrator.__init__`.
  - Updated `execute_multi_persona_review` to record active evaluated personas on `self.personas = list(active_personas)`.
- [x] **Report Generation Parameterization**:
  - Updated `generate_consolidated_report` to accept optional `personas: list[str] | None = None`.
  - Resolved session personas via `personas or (self.personas if self.personas else None) or ["devsecops", "architect", "qa"]`.
  - Serialized the resolved personas into both `findings.json` (`payload_out.personas`) and `candidates.json` (`candidates.personas`).
- [x] **Runner Workflow Integration**:
  - Passed `personas=active_p` to `orchestrator.generate_consolidated_report` in `_run_orchestrator_review`.
- [x] **Unit & Regression Testing**:
  - Added unit test in `tests/test_review_pipeline.py` verifying accurate personas persistence in both `findings.json` and `candidates.json` with structural tuple equality assertions.
  - Validated 100% pass across all 10 quality gates in `uv run devops ci`.
