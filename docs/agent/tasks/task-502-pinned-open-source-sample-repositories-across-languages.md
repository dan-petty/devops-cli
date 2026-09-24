# Task 502: Pinned Open-Source Sample Repositories Across Languages

**Issue**: [#502](https://github.com/dan-petty/devops-cli/issues/502)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

devops ai tooling is meant for any technical project, but every live check so far has used this Python repository and one set of Ansible playbooks. The AST engine claims TypeScript, JavaScript, Go, Rust, Java and HCL, and nothing exercises that on real code.

#### Key Deliverables:
- A checked-in catalog of open-source repositories pinned by commit, with SPDX licence and paths. Categories: Python, TypeScript/JavaScript, Go, Rust, Java, C#/.NET, C/C++, Terraform, Kubernetes/Helm, Dockerfiles, shell and technical documentation. `devops review samples fetch` clones each entry at its commit into `.data/samples/` and verifies the commit and licence file; `devops review samples list` shows the catalog.
- Permissive licences only (MIT, Apache-2.0, BSD), modest sizes, exact commits rather than branches or tags. Fetching needs the network, so it stays out of CI.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
