# Task 311: HashiCorp Vault Native Client, Dynamic Secret Leasing & OS Keyring Envelope Encryption Research

**Issue**: [#311](https://github.com/dan-petty/devops-cli/issues/311)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/security`, `priority/p1-high`

---

## 1. Description & Objectives

Credential resolution was spread across nine hand-written fallback ladders — one per secret — so two credentials could disagree about whether the environment outranked the keyring, and no lookup was observable anywhere. Vault access was read-only with no authentication method and no lease lifecycle, so a dynamic credential issued at the start of a long CI run could lapse mid-operation.

### Key Deliverables Completed:

- [x] **Unified `SecretProvider` Protocol & Resolver (`src/devops_cli/security/secrets.py`)**:
  - `SecretProvider` protocol with `KeyringProvider`, `VaultProvider`, `EnvironmentProvider`, `SettingsProvider`, and `CallableProvider` implementations.
  - `SecretResolver` walks one ordered chain in a single pass for **every** credential: OS keyring (canonical) → Vault (centrally managed) → environment (non-interactive CI) → configuration (last resort).
  - `SecretRef` registry declaring, in one table, where each managed credential may be found — replacing the nine per-getter ladders.
  - A provider that raises is treated as unable to supply, never as fatal, so one unreachable source cannot break resolution.
- [x] **Credential Access Audit Trail**:
  - Every lookup records the logical secret name, the answering provider, and the outcome — **never the value**. A misconfigured precedence or unexpected environment fallback is now observable.
  - Bounded at `CONST_SECRET_AUDIT_MAX_ENTRIES` so long sessions cannot grow without bound.
  - Surfaced through `devops vault audit`.
- [x] **Native Vault Authentication (`src/devops_cli/security/vault_lease.py`)**:
  - AppRole login and in-cluster Kubernetes ServiceAccount login, both issuing typed `VaultAuthResult` values.
  - `VaultAuthResult.client_token` is masked by a Pydantic field serializer, so the issued token cannot travel into CLI output, JSON payloads, or trace spans while remaining usable in-process.
  - All Vault HTTP calls route through the shared, egress-validated broker.
- [x] **Dynamic Secret Lease Lifecycle**:
  - `LeaseRegistry` tracks issued leases with lifetime, renewability, and renewal history.
  - Proactive renewal once a lease burns past `DEFAULT_VAULT_LEASE_RENEW_THRESHOLD` of its TTL, so a long run never presents a lapsed credential.
  - `renew_expiring` sweeps every lease and reports per-lease outcomes; a single failed renewal does not deny the remaining leases their chance.
  - Revocation drops a lease from tracking whether or not Vault accepted it, so a failed revoke cannot leave a stale entry behind.
- [x] **Transit Envelope Encryption**:
  - `transit_encrypt` / `transit_decrypt` wrap values using Vault's Transit engine, so the encryption key never leaves Vault and the workstation holds only ciphertext.
- [x] **New Commands**: `devops vault login` (`--method approle|kubernetes`), `devops vault leases` (`--renew`, `--revoke`), `devops vault audit` (`--json`).
- [x] **Typed Models & Exceptions**: `VaultAuthResult`, `VaultLease`, `VaultLeaseReport` in `src/devops_cli/models/vault.py`; `VaultAuthenticationError` and `VaultLeaseError` with dedicated error codes.
- [x] **Automated Tests & Quality Gates**:
  - 51 unit tests in `tests/test_secret_resolution.py` using structural tuple equality assertions, including explicit assertions that the audit trail never retains a value and that the issued token never serializes.
  - `secrets.py` at 91%, `vault_lease.py` at 95% coverage.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ maintained across all new modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy strict, audit, security, actionlint, docs, uv check, lockfile).
- `devops scan complexity` clean on `secrets.py`, `vault_lease.py`, and `commands/vault.py`.

## Behaviour Change (Pre-1.0 Alpha)

Unifying the ladders changed one credential's observable precedence. `get_logfire_token` previously placed `settings.telemetry.logfire_token` **above** the bare `LOGFIRE_TOKEN` environment variable; under the unified chain the environment outranks committed configuration, consistently with every other secret. A deployment setting both will now resolve the environment value. This is intentional — the environment is the override mechanism — and is covered by an updated assertion in `tests/test_telemetry_logfire.py`.

## Defect Found & Fixed During Implementation

The first iteration cached a settings-bound `SettingsProvider` inside the process-wide resolver, so any later lookup with different settings would silently read a stale configuration snapshot. `SettingsProvider` now resolves settings through a callable, and `SecretResolver.resolve` accepts a per-call `settings_source` that rebinds it. Pinned by `test_cached_resolver_never_serves_a_stale_settings_snapshot`.

## CodeQL Finding Remediated

CodeQL raised `py/clear-text-logging-sensitive-data` (high, CWE-312/532) against the audit
trail's debug log line. The flagged expression carried a credential *identifier* such as
`github.token`, never a value, so the alert was a naming heuristic rather than a leak —
but on a security-scoped module the right response is to make the code unambiguous rather
than suppress the alert. The parameter and record field were renamed `secret_name` →
`credential_id`, which is both more accurate and clears the heuristic, and
`test_audit_debug_log_carries_only_the_credential_identifier` now pins that a credential
value can never reach the emitted log record.

## Scope Note

`hvac` was **not** added as a dependency. The existing `VaultSecretBroker` already speaks the Vault HTTP API through the project's shared, egress-validated HTTP broker, and the auth, lease, and transit endpoints are a handful of documented POST calls. Introducing `hvac` would have added a second HTTP stack that bypasses that egress validation — the wrong trade for a security-scoped module. The native client requirement is satisfied by extending the existing broker path.
