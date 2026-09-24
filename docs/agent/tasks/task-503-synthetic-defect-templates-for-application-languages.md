# Task 503: Synthetic Defect Templates for Application Languages

**Issue**: [#503](https://github.com/dan-petty/devops-cli/issues/503)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

The synthetic defect generator (#415) injects into Python, YAML and Dockerfiles only, so recall cannot be measured on other languages.

#### Key Deliverables:
- Templates for TypeScript/JavaScript, Go, Rust, Java, C# and C/C++: dropped guards and error checks, dropped `await`, disabled TLS verification (`rejectUnauthorized: false`, `InsecureSkipVerify: true`, `danger_accept_invalid_certs(true)`, trust-all callbacks), widened file permissions, and for C/C++ removed bounds checks and unbounded string functions.
- A guard removal takes a complete, balanced block, so the mutated code stays well formed.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
