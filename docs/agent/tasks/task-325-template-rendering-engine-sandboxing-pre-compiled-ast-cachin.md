# Task 325: Template Rendering Engine Sandboxing, Pre-Compiled AST Caching & Variable Validation Research

**Issue**: [#325](https://github.com/dan-petty/devops-cli/issues/325)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

Manifest generation and task tracking file generation use fragmented Jinja2 and string concatenation logic scattered across multiple modules without unified sandboxing.

#### Key Deliverables:
- Context & Rationale*: Manifest generation and task tracking file generation use fragmented Jinja2 and string concatenation logic scattered across multiple modules without unified sandboxing.
- Deep Integration & Functional Extension*: Unify all Kubernetes manifest, Dockerfile, and task documentation rendering under a single `jinja2.SandboxedEnvironment` with pre-compiled AST caching and compile-time variable schema validation.
- Code Optimization & Performance Acceleration*: Eliminate runtime template re-parsing by pre-compiling templates into bytecode; prevent template injection vulnerabilities (CWE-1336) through strict sandboxing; validate all required parameters prior to rendering.
- Refactoring Potential & Legacy Elimination*: Consolidate fragmented template logic across `k8s/`, `docker/`, and `github/` into a centralized `TemplateEngine` service; eliminate ad-hoc string concatenation and brittle regex replacements.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
