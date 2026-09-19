# Task 311: HashiCorp Vault Native Client, Dynamic Secret Leasing & OS Keyring Envelope Encryption Research

**Issue**: [#311](https://github.com/dan-petty/devops-cli/issues/311)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/security`, `priority/p1-high`

---

## 1. Description & Objectives

Workstation secret management uses disparate mechanisms across OS Keyring, environment variables, and shallow Vault CLI invocations, lacking automated lease lifecycle management.

#### Key Deliverables:
- Context & Rationale*: Workstation secret management uses disparate mechanisms across OS Keyring, environment variables, and shallow Vault CLI invocations, lacking automated lease lifecycle management.
- Deep Integration & Functional Extension*: Native asynchronous Vault client integration (`hvac` / async HTTP) with Kubernetes service account and AppRole authentication; background daemon for proactive secret lease renewal; Vault Transit engine integration for zero-knowledge envelope encryption of local workstation credentials.
- Code Optimization & Performance Acceleration*: Eliminate expired credential failures in long-running CI/CD runs via automated token lease renewal; eliminate plaintext secret staging in memory buffers; unify local and remote credential resolution into a single-pass lookup.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/commands/vault.py` and security modules to implement a unified `SecretProvider` protocol; eliminate fragmented keyring vs. env fallback ladders; centralize audit logging of credential accesses.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
