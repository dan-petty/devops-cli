# Task 791: Review PR Post Without Reporting Preserves Findings and Personas

**Issue**: [#791](https://github.com/dan-petty/devops-cli/issues/791)
**Scope**: `type/bug`, `scope/review`, `priority/p2-medium`
**Feasibility**: Verified against `ai/review/runner.py` (_report_review and _record_review_metrics), `ai/review/pipeline.py` (generate_consolidated_report and _collect_and_deduplicate_findings), and `ai/review_schema.py` (Finding and SavedFinding models).

---

## 1. Description & Objectives

Resolves an issue where `devops review pr --post --no-reporting` posts a GitHub PR comment stating "Zero findings identified." and emits zero `FINDINGS_TOTAL` metrics even when verified and admitted scanner findings were detected during review. Additionally preserves the specific persona attribution across findings so metrics record each finding's actual persona rather than defaulting all findings to a single default persona.

#### Key Deliverables:
- In `src/devops_cli/ai/review/runner.py`: update `_report_review` to collect verified findings from payloads and admitted scanner findings when reporting is skipped, preserving `persona` on each finding.
- In `src/devops_cli/ai/review/runner.py`: update `_record_review_metrics` to attribute findings in `FINDINGS_TOTAL` to each finding's specific persona label.
- In `src/devops_cli/ai/review_schema.py`: add optional `persona` and `persona_title` fields on `Finding` with `SkipJsonSchema` to prevent field stripping during model validation.
- Unit and integration tests feeding real orchestrator review output into PR comment formatting and metrics recording, verifying behavior with and without `--no-reporting` and with `--no-static-scan`.
- Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ enforced.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

## 2. Acceptance Criteria
- [x] Criterion 1: The PR review comment and finding metrics are built from verified findings whether or not the reporting stage runs (`--no-reporting`).
- [x] Criterion 2: Finding persona attribution is kept, and finding metrics in `FINDINGS_TOTAL` carry each finding's own persona label.
- [x] Criterion 3: Tests feed real `_run_orchestrator_review` output into the comment formatter and metrics recorder, validating runs with and without `--no-reporting` and with `--no-static-scan`.
- [x] Criterion 4: The static analyzer line in zero-findings comments continues to show only scanners that actually ran, preserving #657 behavior.
- [x] Changelog fragment authored at `changelog.d/791.md`; `uv run devops ci` passes 100%.
