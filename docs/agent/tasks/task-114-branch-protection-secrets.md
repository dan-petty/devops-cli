# Task 114: Declarative Branch Protection Auditor & Repository Secret Synchronization

**Issue**: [#114](https://github.com/dan-petty/devops-cli/issues/114)
**PR**: [#197](https://github.com/dan-petty/devops-cli/pull/197)
**Status**: In Review
**Milestone**: `v0.2.17`
**Priority**: `priority/p2-medium`
**Scope**: `scope/github`

---

## 1. Description & Architectural Objectives

Implement declarative branch protection policy enforcement and libsodium-encrypted repository secret synchronization:
1. **Declarative Branch Protection Policies (`devops gh branch-protection audit|sync`)**:
   - Define declarative branch protection specifications in YAML (`.github/branch-protection.yml`).
   - Audit existing branch protection rulesets against desired policies, reporting compliance and drift with Rich formatters.
   - Synchronize branch protection rulesets via GitHub REST API, supporting `--dry-run` and per-branch targeting.
2. **Libsodium-Sealed Repository Secrets (`devops gh secrets sync`)**:
   - Retrieve secrets from OS Keyring or HashiCorp Vault.
   - Encrypt secret values using libsodium sealed-box public key encryption (`PyNaCl`).
   - Synchronize encrypted secrets to GitHub Actions repository secrets via REST API (`PUT /repos/{owner}/{repo}/actions/secrets/{secret_name}`).
   - Support `--dry-run`, ensuring zero leakage of secret values in logs, outputs, or error details.
3. **Engineering Standards & Architectural Invariants**:
   - Strict cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ project-wide.
   - Comprehensive unit and integration test coverage $\ge 90\%$.
   - Bounded string truncation ($\le 256$ chars) on all error details.

---

## 2. Planned Changes

1. **`.github/branch-protection.yml`**:
   - Declarative branch protection policy specification for `main` and `release/*`.
2. **`src/devops_cli/github/branch_protection.py`**:
   - Models: `BranchProtectionPolicy`, `StatusChecksPolicy`, `ReviewsPolicy`, `BranchProtectionAuditResult`, `BranchProtectionSyncResult`.
   - Loader: `load_branch_protection_policies(path: Path) -> list[BranchProtectionPolicy]`.
   - Engine: `audit_branch_protection(...)` and `sync_branch_protection(...)`.
3. **`src/devops_cli/github/secrets.py`**:
   - Models: `GitHubPublicKey`, `SecretSyncItem`, `SecretSyncResult`.
   - Encryption: `encrypt_secret(public_key_b64: str, secret_value: str) -> str` using `nacl.public.SealedBox`.
   - Fetchers: `get_repo_public_key(...)`, `resolve_secret_value(name: str, source: str, ...) -> str | None`.
   - Engine: `sync_repository_secrets(...)`.
4. **`src/devops_cli/github/__init__.py`**:
   - Export new symbols and models.
5. **`src/devops_cli/commands/gh.py`**:
   - Add `branch-protection` subcommand group (`audit`, `sync`).
   - Add `secrets` subcommand group (`sync`).
6. **`src/devops_cli/lang/en/help.py`**:
   - Add command help strings to `GHCommandHelp`.
7. **`tests/test_github_branch_protection.py` & `tests/test_github_secrets.py`**:
   - Comprehensive test suites with $\ge 90\%$ code coverage.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#114) with `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-114-branch-protection-secrets.md`.
- [x] Checkout dedicated topic branch `feat/114-branch-protection-secrets`.
- [x] Author declarative policy template `.github/branch-protection.yml`.
- [x] Implement `src/devops_cli/github/branch_protection.py`.
- [x] Implement `src/devops_cli/github/secrets.py`.
- [x] Register CLI subcommands in `src/devops_cli/commands/gh.py` and update `help.py`.
- [x] Author unit tests in `tests/test_github_branch_protection.py` and `tests/test_github_secrets.py`.
- [x] Run quality gates (`devops scan complexity`, `ruff`, `mypy`, `pytest`, `devops docs generate --check`).
- [x] Commit changes, push branch, and open Draft Pull Request to `release/v0.2.17` ([#197](https://github.com/dan-petty/devops-cli/pull/197)).
- [ ] Monitor CI checks, transition PR to ready, address review threads, and squash-merge into `release/v0.2.17`.
