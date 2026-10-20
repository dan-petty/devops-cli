# Task: Related Review Findings are Linked Across Groups and One Plan Orders Work (#1148)

**Issue**: [#1148](https://github.com/dan-petty/devops-cli/issues/1148)
**Scope**: scope/review
**Feasibility**: Checked findings data model and existing group analysis pipeline in `src/devops_cli/review/analysis.py` alongside `ai/review/ast_imports.py` and the 10 review loop runs (S12–S21). The loop findings in `k8s/llm/profiles/ollama-profiles.yaml` produce 9 DaemonSets with identical rule families and manifest sources, while Python findings share AST symbol components. Cross-group keys are deterministically derivable without calling an LLM or modifying underlying scanner runners.

## Description

- [x] Deterministic cross-group keys extracted across findings: CWE identifiers, rule family, symbol-graph component via `ai/review/ast_imports.py`, purl, and manifest source.
- [x] Correlation table generated in `analysis.json` and rendered in `review.md`.
- [x] G10 verification check rejects any group analysis claiming a "same root cause" relation or statement between findings that do not share a correlation key.
- [x] Review-level remediation plan stage (`run_review_plan_job`) takes checked group analysis outputs and correlation table to produce a comprehensive plan covering all admitted findings under G10 validation.
- [x] Plan orders steps with introduced findings first, then by severity rank (CRITICAL down to INFO), then by file path, line number, and fingerprint.
- [x] Groups related resources (such as the 9 DaemonSets in `k8s/llm/profiles/ollama-profiles.yaml`) under a single remediation plan step.
- [x] Property test validates that admitted findings, `findings.json`, and `findings.sarif` remain identical whether the analysis stage is enabled or disabled.
- [x] All unit and integration tests run offline with recorded fakes in <1s per test without network, real scanners, or live models.
- Pending a person: verify on live loop input that the review plan presents the 9 DaemonSets under one consolidated step in the pull request review.
