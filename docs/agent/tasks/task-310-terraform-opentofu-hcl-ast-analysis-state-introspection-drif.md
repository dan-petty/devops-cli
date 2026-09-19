# Task 310: Terraform & OpenTofu HCL AST Analysis, State Introspection & Drift Optimization Research

**Issue**: [#310](https://github.com/dan-petty/devops-cli/issues/310)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Infrastructure as Code commands execute full `tofu` / `terraform` binary runs for static checks, incurring substantial startup latency and disk I/O for simple plan and drift inspections.

#### Key Deliverables:
- Context & Rationale*: Infrastructure as Code commands execute full `tofu` / `terraform` binary runs for static checks, incurring substantial startup latency and disk I/O for simple plan and drift inspections.
- Deep Integration & Functional Extension*: In-process HCL AST parsing (`python-hcl2`) and state file JSON schema introspection (`terraform.tfstate`) to inspect resource graphs, analyze attribute references, detect configuration drift, and calculate cost estimations without spawning binary CLI processes for read-only queries.
- Code Optimization & Performance Acceleration*: Accelerate IaC drift detection and configuration linting by 90%+ by bypassing CLI binary initialization; construct direct topological resource DAGs in memory for instant blast-radius visualization.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/commands/tf.py` into a declarative IaC analysis service; remove repetitive CLI argument list builders; replace ad-hoc regex cost estimation with a typed Infracost schema parser.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
