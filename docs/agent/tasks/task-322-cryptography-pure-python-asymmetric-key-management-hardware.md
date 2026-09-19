# Task 322: Cryptography Pure-Python Asymmetric Key Management & Hardware Token Authentication Research

**Issue**: [#322](https://github.com/dan-petty/devops-cli/issues/322)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.22`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

SSH key generation and TLS certificate management currently shell out to external `ssh-keygen`, `ssh-keyscan`, and `openssl` binaries, creating cross-platform portability and error handling issues.

#### Key Deliverables:
- Context & Rationale*: SSH key generation and TLS certificate management currently shell out to external `ssh-keygen`, `ssh-keyscan`, and `openssl` binaries, creating cross-platform portability and error handling issues.
- Deep Integration & Functional Extension*: Pure Python cryptographic operations using `cryptography` for Ed25519/RSA key generation, X.509 certificate authority creation, and TLS cert validation with zero OpenSSL subprocess dependency; native SSH agent client integration via async SSH sockets; hardware token (FIDO2/PKCS#11) inspection.
- Code Optimization & Performance Acceleration*: Eliminate external OpenSSL / OpenSSH binary dependencies for key generation and certificate verification; eliminate subprocess spawn overhead during batch key validation; improve cryptographic auditability.
- Refactoring Potential & Legacy Elimination*: Refactor `src/devops_cli/ssh/` and `src/devops_cli/tls/` into a consolidated, audited cryptographic service layer; remove legacy subprocess wrappers and temporary file staging.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
