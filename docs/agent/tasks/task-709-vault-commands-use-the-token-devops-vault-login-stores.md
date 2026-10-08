# Task: Vault commands use the token `devops vault login` stores (#709)

**Issue**: [#709](https://github.com/dan-petty/devops-cli/issues/709)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: type/bug, scope/security, priority/p1-high

## Description

`devops vault login` stored the token it obtained, but nothing read it back: every Vault command
built a broker with no token. `vault get` then answered silently from the keyring, `vault sync`
reported "Synchronized 0 secret(s)", `vault set` and `vault leases --revoke` failed with no reason,
and `gh secrets sync --source vault` uploaded the local keyring value labelled as Vault's.

The broker now resolves its token in the order the shared chain gives every secret (argument, the
stored login, `VAULT_TOKEN`, `DEVOPS_CLI_VAULT_TOKEN`), through the shared resolver, and the
stored token is bound to the address and namespace that issued it. Reading a stored token by
default widened where a token could be sent, so the same change stops `vault status` from sending
one, and holds every Vault request, login included, to the Vault origin on every redirect hop.
Reads report which source answered; a missing, rejected or misdirected token fails the command
instead of falling back. `vault login --store` fails when no OS keyring can keep the token, and a
new `vault logout` revokes and deletes it.

## Acceptance Criteria

### Token resolution

- [x] `VaultSecretBroker` resolves argument, then the keyring record (only for its own address and namespace), then `VAULT_TOKEN`, then `DEVOPS_CLI_VAULT_TOKEN`; the docstring states the order (`tests/test_vault_broker.py`: `test_stored_login_supplies_the_token_when_the_environment_has_none`, `test_keyring_outranks_the_environment_and_the_argument_outranks_both`, `test_devops_cli_vault_token_is_the_last_source`).
- [x] `vault login` stores one record under `CONST_VAULT_LOGIN_KEYRING_KEY` holding the token, the normalized address and the namespace (`test_login_stores_one_record_bound_to_the_issuing_vault`); a bare-string entry is unusable and the message says to log in again (`test_a_bare_token_entry_is_unusable`). No migration.
- [x] The record and the environment are looked up through the shared resolver with two `SecretRef`s that carry no `vault_path`; `devops vault audit` records each lookup the broker makes, by name (`test_token_lookups_are_audited_by_name_never_by_value`), and `VaultProvider` builds no second broker (`test_resolving_the_broker_token_builds_no_second_broker`).
- [x] The broker records the token source and why a stored token was skipped, never the value (`VaultTokenSource`).
- [x] `vault status` needs no token and shows a Token row naming the source, or the address a skipped token was issued for (`test_vault_status_names_the_stored_token`, `test_vault_status_names_the_address_a_skipped_token_was_issued_for`).
- [x] Dry runs of `get`, `set`, `sync` and `leases` include the token source and make no request, with or without a token (`test_dry_runs_name_the_token_source_and_make_no_request`).

### Where a token is sent

- [x] `get_status` never sends `X-Vault-Token`, for `vault status --addr` and for the MCP `vault_status` tool (`test_status_never_sends_a_token`, `test_mcp_vault_status_never_sends_a_token`).
- [x] A stored token is sent only to the address and namespace it was issued for; otherwise the environment token is used, and without one the command fails as "no token" naming the issuing address (`test_stored_login_for_another_vault_is_never_sent`).
- [x] Every Vault request, in the broker and in `vault_lease._post`, goes through `security/vault_http.vault_request`, which sets a same-origin policy on `CONST_HTTP_EGRESS_POLICY_EXTENSION`; a 307 to another origin is refused for a token GET and for an AppRole login POST, nothing reaches the second origin, and the error names it; a same-origin redirect is still followed (`test_a_redirect_to_another_origin_is_refused`, `test_a_login_body_never_follows_a_redirect_to_another_origin`, `test_a_same_origin_redirect_is_followed`).
- [x] `vault sync` never writes the login-token key and says it skipped it (`test_sync_reads_vault_alone_and_never_writes_the_login_key`, `test_vault_sync_reports_the_skipped_login_key_and_missing_fields`).
- [x] The MCP tools that act with a token (`vault_get`, `vault_set`, `vault_sync`) take no address (`test_the_token_carrying_vault_tools_take_no_address`).

### Missing or rejected token

- [x] With no usable token, `vault set`, `vault sync` and every `vault leases` mode exit 1 before any request, naming `devops vault login`, `VAULT_TOKEN` and `DEVOPS_CLI_VAULT_TOKEN` in the missing/rejected wording of #465 (`test_commands_needing_a_token_exit_before_any_request_without_one`).
- [x] A 401 or 403 exits 1, naming the token's source, the status, the expired/revoked/no-policy hint and `devops vault login`, with no keyring fallback (`test_a_rejected_token_raises_and_never_falls_back`, `test_vault_get_on_a_rejected_token_exits_without_reading_the_keyring`, `test_leases_revoke_with_a_rejected_token_names_its_source`).
- [x] A refused `vault leases --revoke X` prints the HTTP status (`test_leases_revoke_refusal_names_the_status`).

### Vault-only reads

- [x] `vault get` reads Vault with a token and falls back to the keyring only with no usable token, on a 404 or a missing field, or when Vault is unreachable; the output names the answering source, and the not-found message names only the sources checked (`test_no_value_in_vault_falls_back_to_the_keyring`, `test_an_unreachable_vault_falls_back_to_the_keyring`, `test_vault_get_not_found_names_only_the_sources_checked`, `test_vault_get_on_a_404_answers_from_the_keyring_and_says_so`).
- [x] `vault sync` reads Vault only; a path with no secret exits 1 (`test_vault_sync_of_an_empty_path_exits_1`).
- [x] `devops gh secrets sync --source vault` reads Vault only: a rejected token fails the command through its handler and nothing is uploaded; an absent key is missing and never read from the keyring (`tests/test_github_secrets.py`).
- [x] `VaultProvider` reads Vault only, makes no request without a token, and returns None on a 403 (`test_vault_provider_without_a_token_makes_no_request`, `test_vault_provider_with_a_rejected_token_answers_none`).

### Login and logout

- [x] With `--store`, `vault login` checks for an encrypted, unlocked keyring before the login request and exits 1 naming `--no-store` and the CI/pod `VAULT_TOKEN` route when there is none (`test_login_without_a_persistent_keyring_exits_before_logging_in`), and exits 1 when the keyring refuses the write (`test_login_fails_when_the_keyring_refuses_the_token`). `--no-store` exits 0 and stores nothing. The token is never printed.
- [x] The `--no-store` and `--method` help name the no-store form for CI and in-cluster runs.
- [x] `devops vault logout` revokes at the stored address and namespace (`auth/token/revoke-self`, `CONST_VAULT_PATH_TOKEN_REVOKE_SELF`) even when `VAULT_ADDR` points elsewhere, then deletes the record; with Vault unreachable it still deletes and says the revoke did not happen; with no record it says so and exits 0; a bare entry is deleted without being sent anywhere; a dry run sends and deletes nothing (`tests/test_vault_cmd.py`, logout section).

### Types

- [x] `LeaseRegistry.token` and the `token` of `transit_encrypt` and `transit_decrypt` are a required `str`; `vault leases` passes `broker.require_token()`.

### Tests

- [x] Offline only: `HttpClientBroker.request` patched, or `stub_web` for redirects (`StubWeb.redirect` takes a status); `example.com` hosts only.
- [x] `test_registry_headers_omit_absent_credentials` is replaced by `test_registry_headers_always_carry_the_token`; the fallback, revoke, `VaultProvider` and gh tests that pinned the old behaviour changed with it.
- [x] No test leaves a Vault token behind: the autouse `isolate_vault_token` fixture clears the login entry from the in-process store in place, resets the process-wide resolver (whose `VaultProvider` keeps its broker) and drops the session lease registry.
- [x] `uv run devops ci` passes.

### Person-run check (needs a dev Vault)

- Pending a person: `devops vault login --method approle --role-id <id> --secret-id <secret>`, then `devops vault status` shows `Token  keyring`; `devops vault get <path>` answers "(from vault)"; with `VAULT_ADDR` set to another address, `devops vault status` shows `none (stored token not used: issued for <address>)`; after `devops vault logout`, `devops vault get <path>` says "Vault was not consulted: no usable token".

## Decisions and deviations

- **Login checks the keyring first (amendment).** `vault login --store` calls `require_persistent_keyring()` before the login request and stores the record with `keyring_write()` (both added in v0.2.26), rather than reading `set_keyring_secret`'s bool or the in-memory store. No orphan token is issued when the keyring cannot keep it. `keyring_delete()` was added beside them for logout (`keyring.delete_password`; `PasswordDeleteError` means absent).
- **Audit wording (amendment).** The audit records each token lookup the broker makes: when the stored record wins, the environment is not looked up.
- **Locked keyring reads as no stored token.** The record is read through the shared resolver, as the issue requires, and `_keyring_get` logs "the OS keyring is locked; run `devops devcontainer unlock-keyring`" and answers None. The broker then has no stored token and the Token row says `none`; the warning names the lock (`test_a_locked_keyring_reads_as_no_stored_token`). `vault logout` reads with `keyring_read` and fails on a locked keyring instead of claiming there is no token.
- **Outcomes the issue left open.** A 200 whose secret lacks the requested field counts as "no value in Vault", like a 404: `vault get` falls back to the keyring and says so, and Vault-only reads report it missing. Any other non-2xx status (a sealed Vault's 503, 429, 400) and a body that is not JSON secret data raise `VaultOperationError` with no fallback. "Unreachable" is an `httpx2.TransportError`, raised as the new `VaultUnreachableError`.
- **One Vault HTTP path.** `security/vault_http.py` holds `vault_request`, used by the broker and by `vault_lease._post`. It passes `extensions={CONST_HTTP_EGRESS_POLICY_EXTENSION: same_origin_policy(addr)}`, comparing `httpx2.URL.origin` values (a library call), and keeps `allow_private_network=True`. #898 replaces that per-request flag with a private-allowed Vault client; whichever lands second moves `vault_request` onto it and keeps the policy extension, which the broker's request hook applies on every hop.
- **`VaultLeaseError` carries `status_code`**, and `LeaseRegistry.revoke` raises it instead of logging and returning False. `revoke_all` returns the ids Vault refused. `vault login` now reports a Vault refusal of the login through `exit_on_error(VaultError)` instead of a traceback.
- **`vault logout`** honours the global dry run, as `login` and `leases` do. It deletes a bare or unreadable entry without sending it anywhere, since that entry names no Vault, and says it was not revoked. It exits 0 when only the revoke failed; it exits 1 when the keyring cannot be read or the entry cannot be deleted.
- **`vault sync`** exits 1 when a requested field has no value in Vault or the keyring refuses a write, listing them; it no longer prints "Synchronized 0 secret(s)" for a path with no secret.
- **`gh secrets sync --source vault --dry-run` no longer reads Vault.** With the stored token now used by default, that dry run would have started sending Vault requests for every logged-in user, against the rule that a dry run makes no request (#412). It now lists each secret it would read, seal and upload. The keyring source's dry run still reads the local keyring, as before.
- **MCP.** #857 has not shipped, so `vault_set` and `vault_sync` carry no mutating annotation while they now act with the stored token. As the issue decided, no other gate is added: the address binding and the redirect refusal keep the token on the configured Vault, and the signature test keeps an address parameter off the token-carrying tools.
- **Long-lived processes.** `VaultProvider` keeps the broker it built, so an MCP server or service resolves the token once and sees a later `vault login` or `vault logout` only after a restart. A revoked token only makes Vault lookups answer None.
- **Token source names** reuse `CONST_SECRET_PROVIDER_KEYRING` and `CONST_SECRET_PROVIDER_ENVIRONMENT`, with `argument` and `none` beside them. The stored record (`VaultStoredLogin`) serializes its token, unlike `VaultAuthResult`, and keeps it out of `repr` with `Field(repr=False)`.

## Deliverables

- [x] `src/devops_cli/security/vault_broker.py`: token resolution and binding, `require_token`, `status_error`, `read_secret` (Vault only), `get_secret` returning `VaultSecretLookup`, raising `set_secret`, `sync_to_keyring` returning `VaultSyncReport`, unauthenticated `get_status`.
- [x] `src/devops_cli/security/vault_http.py`: `vault_request`, `same_origin_policy`, `vault_url`.
- [x] `src/devops_cli/security/vault_lease.py`: `_post` through `vault_request` with the status on `VaultLeaseError`; required `token`; raising `revoke`; `revoke_self`.
- [x] `src/devops_cli/security/secrets.py`: `VaultProvider` reads Vault only.
- [x] `src/devops_cli/github/secrets.py`: Vault-only source; dry run makes no Vault request.
- [x] `src/devops_cli/commands/vault.py`: Token row, token source in dry runs, source-naming `get`, failing `set`/`sync`/`leases`, keyring-checked `login`, new `logout`.
- [x] `src/devops_cli/config/constants.py`, `config/settings.py` (`keyring_delete`), `models/vault.py`, `exceptions/vault.py` (`VaultUnreachableError`, widened `VaultAuthenticationError`).
- [x] Tests: `tests/test_vault_broker.py`, `tests/test_vault_cmd.py`, `tests/test_secret_resolution.py`, `tests/test_github_secrets.py`, `tests/test_fastmcp_contracts.py`, `tests/conftest.py`, `tests/web_fakes.py`.
- [x] Generated docs: `docs/CLI_REFERENCE.md`, `docs/commands/vault.md`, `docs/ERRORS.md`, `README.md`.
- [x] Changelog fragment: `changelog.d/709.md`.
