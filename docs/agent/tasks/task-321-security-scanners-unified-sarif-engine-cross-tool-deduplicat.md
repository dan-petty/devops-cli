# Task 321: Security Scanners Unified SARIF Engine, Cross-Tool Deduplication & AST Autofix Synthesis Research

**Issue**: [#321](https://github.com/dan-petty/devops-cli/issues/321)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/security`, `priority/p1-high`

---

## 1. Description & Objectives

Security scanning executes Trivy, Semgrep, Gitleaks, Checkov, and Bandit independently via separate subprocesses, each with custom regex/JSON parsers and disparate finding schemas.

#### Key Deliverables:
- Context & Rationale*: Security scanning executes Trivy, Semgrep, Gitleaks, Checkov, and Bandit independently via separate subprocesses, each with custom regex/JSON parsers and disparate finding schemas.
- Deep Integration & Functional Extension*: Unified SARIF (Static Analysis Results Interchange Format) ingestion and normalization engine that correlates, deduplicates, and ranks findings across all scanners; intelligent AST-based auto-remediation synthesis (`devops scan fix`); suppression policy inheritance across repositories.
- Code Optimization & Performance Acceleration*: Eliminate redundant scanner runs across overlapping file subsets; replace 5 disparate output format parsers with a single, high-performance streaming SARIF parser; generate minimal AST-level autofix patches.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/commands/scan.py` using a strategy pattern with a unified `BaseSecurityScanner` interface; eliminate duplicate subprocess runners and custom regex parsers; standardize finding taxonomy and severity models.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
