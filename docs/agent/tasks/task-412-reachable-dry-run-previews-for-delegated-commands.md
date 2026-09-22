# Task 412: Reachable `--dry-run` Previews for Delegated Commands

**Issue**: [#412](https://github.com/dan-petty/devops-cli/issues/412)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Every command group is registered lazily as a module path, and the lazy proxy short-circuits under dry-run: it prints the command line you typed and returns without loading the target module. So no command in the CLI ever reaches its own dry-run branch. 160 of 306 registered commands contain one — detailed previews of exactly what would be written — and none of them is reachable from the command line. `devops k8s configure-urls --dry-run` had eight hardcoded NodePort URLs pointing at a minikube node nobody in this project uses, and the reason it went unnoticed is that the block could not be reached.

#### Key Deliverables:
- Context & Rationale*: Every command group is registered lazily as a module path, and the lazy proxy short-circuits under dry-run: it prints the command line you typed and returns without loading the target module. So no command in the CLI ever reaches its own dry-run branch. 160 of 306 registered commands contain one — detailed previews of exactly what would be written — and none of them is reachable from the command line. `devops k8s configure-urls --dry-run` had eight hardcoded NodePort URLs pointing at a minikube node nobody in this project uses, and the reason it went unnoticed is that the block could not be reached.
- Deliverable*: Delegate under dry-run so a command renders its own preview, with the generic line kept for commands that have none.
- Constraint*: The short-circuit is load-bearing. 146 registered commands have no dry-run branch, and delegating to those would execute them for real under a flag that promises the opposite. Each has to be classified — read-only, or needing a branch — before the switch flips, so the audit is the work and the switch is the last step.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
