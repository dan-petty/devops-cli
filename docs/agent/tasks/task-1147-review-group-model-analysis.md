# Task: Grounded Model Analysis and Plan per Finding Group (#1147)

**Issue**: [#1147](https://github.com/dan-petty/devops-cli/issues/1147)
**Status**: Done
**Milestone**: v0.2.36
**Priority**: priority/p1-high
**Scope**: scope/ai, scope/review
**Feasibility**: Verified against `src/devops_cli/review/admission.py` (`AdmittedFinding` frozen dataclass), `src/devops_cli/review/anchors.py` (`RegionAnchor`, `ObjectAnchor`, `AdvisoryAnchor`), `src/devops_cli/ai/review/pipeline.py` (`ReviewPipelineOrchestrator`), `src/devops_cli/review/score.py` (`ScoreReport.run_metrics`), and `src/devops_cli/ai/run_store.py` (`RegressionTolerances` and `_SCORE_DROP_METRICS`).

## Description

Add bounded per-group model analysis for admitted findings (`src/devops_cli/review/analysis.py`), kept strictly separate from `findings.json` and `findings.sarif`. Each group of related findings receives a single model call grounded in the rule's documentation at the installed tool version, the enclosing symbol or anchor excerpt (sanitized with `mask_secrets`), and environment facts. Every quote, citation, version, and code block in the model's structured reply is verified by deterministic G10 checks before appearing in `analysis.json` and the `## Model Analysis (Model-Written)` section of `review.md`. Also fold in `#1138`'s reference coverage tolerance (`reference_coverage` in `ScoreReport.run_metrics` and `--max-reference-coverage-drop` in `devops ai runs check`).

## Key Changes

- **Grouping (`group_findings_for_analysis` in `src/devops_cli/review/analysis.py`)**:
  - Groups admitted findings deterministically into three group kinds (`symbol`, `object`, `purl`):
    - Region-anchored findings sharing `(path, enclosing_symbol)` (extracted via Python AST when available) or `(path, rule_id)` when at module top level.
    - Kubernetes findings (`kube-linter`, `pluto`, `kubeconform` or `ObjectAnchor`) sharing `(namespace, kind, name)`.
    - Dependency advisory findings (`osv`, `pip-audit`, `trivy` or `AdvisoryAnchor`) sharing `purl`.
- **Bounded Reference Input & Secret Masking (`build_analysis_job_input`)**:
  - Passes each finding's rule ID, message, and secret-masked anchor excerpt (`mask_secrets`) with $\pm 10$ context lines (`DEFAULT_ANALYSIS_ANCHOR_CONTEXT_LINES`), plus the enclosing Python function/class source when applicable.
  - Passes rule documentation keyed as `rule:<tool>:<rule_id>@<version>` at the installed tool version (`resolve_rule_doc`), relevant knowledge-base manuals (`kb:<name>`), and environment facts (`language_floor`, `python_pin`, `kubernetes_version`, `suppression_path`).
  - Enforces a character budget (`DEFAULT_ANALYSIS_REFERENCE_BUDGET_CHARS = 16000`), recording `needed_keys`, `received_keys`, `dropped_keys` (`budget` or `unavailable`), and `reference_coverage = |received_keys| / |needed_keys|`.
- **Strict Structured Output Schema (`GroupAnalysisOutput`)**:
  - Enforces `ConfigDict(extra="forbid", frozen=True)` with `explanation`, `root_cause`, `related_items` (requiring `relation` in `same_symbol`, `same_pattern`, `same_dependency`, `same_workload`, `shared_cause` and a non-empty `note`), `plan_steps` (ordered remediation steps citing member `finding_ids` and optional `code_block`), `doc_quotes`, `code_quotes`, and `suppression_note`.
  - Rejects `diff`, `state`, `severity`, `location`, and `new_finding` at the schema boundary.
- **Deterministic G10 Verification (`verify_group_analysis`)**:
  - Rejects outputs on: (1) `doc_quote_mismatch` (quote not a substring of `received_keys` docs), (2) `code_quote_mismatch` (quote not a substring of the group's anchor/symbol excerpts), (3) `unknown_related_id` (related item or plan step cites a finding ID outside the group), (4) `code_block_syntax_error` (fenced/step Python code block fails `ast.parse` at the project's Python floor), (5) `ungrounded_version_number` (version string absent from environment facts, rule docs, and excerpts), and (6) `wrong_suppression_syntax` (suppression note fails to cite `.devops/review.toml` and `expires` when suppression is recommended).
  - Counts rejections by reason in `analysis.json` (`rejections`).
- **Execution & Separation from Findings (`run_group_analysis`, `ReviewPipelineOrchestrator`)**:
  - Dispatches at most one model call per group through `ReviewWorkerPool` capped at `DEFAULT_GATEWAY_REVIEW_CONCURRENCY`, recording `temperature`, `top_p`, and `seed` in `analysis.json`.
  - Writes `analysis.json` in the session directory and renders `## Model Analysis (Model-Written)` in `review.md`, naming any rule documentation dropped for budget.
  - Leaves `findings.json` and `findings.sarif` untouched and byte-identical whether `group_analysis` is enabled or disabled.
- **Reference Coverage Scoring & Regression Gate (`score.py`, `run_store.py`, `ai_runs.py`)**:
  - `score_sessions` reads `reference_coverage` from `analysis.json` when present and pools it into `ScoreReport.run_metrics()["reference_coverage"]`.
  - `RegressionTolerances` gains `max_reference_coverage_drop: float = 0.0` (`_SCORE_DROP_METRICS["reference_coverage"]`), exposed on `devops ai runs check` via `--max-reference-coverage-drop`.

## Acceptance Criteria

- [x] Admitted findings are grouped deterministically by enclosing symbol/rule (`symbol`), Kubernetes `(namespace, kind, name)` (`object`), or package `purl` (`purl`).
- [x] Each group receives at most one model call via `ReviewWorkerPool` capped at `DEFAULT_GATEWAY_REVIEW_CONCURRENCY`, with anchor excerpts passed through `mask_secrets`.
- [x] Reference inputs track `needed_keys`, `received_keys`, `dropped_keys` (`budget` / `unavailable`), and `reference_coverage`, naming budget-dropped rule docs in `review.md`.
- [x] `GroupAnalysisOutput` forbids `diff`, `state`, `severity`, `location`, and `new_finding`, and requires a relation and note on every `RelatedItem`.
- [x] `verify_group_analysis` enforces all 6 G10 checks and records rejection counts by reason in `analysis.json`.
- [x] `findings.json` and `findings.sarif` remain byte-identical with `group_analysis` on vs off, while `analysis.json` and the `## Model Analysis (Model-Written)` section in `review.md` hold the verified model analysis.
- [x] `ScoreReport.run_metrics()` pools `reference_coverage` when `analysis.json` is present, and `devops ai runs check --max-reference-coverage-drop` gates regressions on it.
