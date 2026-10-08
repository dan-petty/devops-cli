# `devops vault`

Enterprise HashiCorp Vault secret broker

## Commands

## `devops vault status`

**Inspect HashiCorp Vault cluster health and initialization status.**

Inspect HashiCorp Vault cluster health and initialization status.

The health endpoint needs no token, and none is sent. The Token row names where the token
other commands would use comes from, and why a stored token is not used for this address.

```bash
devops vault status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--addr`, `-a` | `string` | - | Vault cluster HTTP API address |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops vault get`

**Fetch a secret from Vault, or from the OS keyring when Vault cannot answer.**

Fetch a secret from Vault, or from the OS keyring when Vault cannot answer.

The keyring answers only with no usable token, when Vault has no value at the path, or when
Vault is unreachable; never after Vault rejects the token. The output names the source.

```bash
devops vault get [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Vault secret path (e.g. secret/data/myapp or vault://secret/data/myapp#token) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key`, `-k` | `string` | - | Specific secret field key to extract |
| `--show` | `boolean` | - | Display secret in plain text without masking |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops vault set`

**Store secret key-value pairs in HashiCorp Vault KV-v2 engine.**

```bash
devops vault set [OPTIONS] <path> <key_values>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Vault secret path (e.g. secret/data/myapp) |
| `<key_values>` | `string` | Yes | Key-value pairs to store (format: KEY=VALUE) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops vault sync`

**Synchronize secrets from Vault into OS Keyring for offline/local CLI operations.**

Synchronize secrets from Vault into OS Keyring for offline/local CLI operations.

Reads Vault alone. A path with no secret fails, and a field named like the entry that holds
the `devops vault login` token is never written.

```bash
devops vault sync [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Vault secret path to synchronize into OS Keyring |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key`, `-k` | `string` | - | Specific keys to sync (syncs all keys if omitted) |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops vault login`

**Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount.**

Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount.

With --store, the default, the token is kept in the OS keyring with the address and namespace
that issued it, and other vault commands use it for that Vault only. The command fails before
logging in when no encrypted, unlocked OS keyring can keep it. The token is never printed.

```bash
devops vault login [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--method`, `-m` | `string` | `approle` | Authentication method: approle or kubernetes. In a pod, use kubernetes with --no-store: it checks the ServiceAccount login without keeping the token, and the pod takes VAULT_TOKEN from its Vault integration. |
| `--role` | `string` | - | Vault role name (kubernetes method) |
| `--role-id` | `string` | - | AppRole role_id |
| `--secret-id` | `string` | - | AppRole secret_id |
| `--store` / `--no-store` | `boolean` | `True` | Keep the issued token in the OS keyring, for this Vault address and namespace only. --no-store checks the credentials without keeping the token: the form for CI and in-cluster runs, which take VAULT_TOKEN from their Vault integration. |

---

## `devops vault logout`

**Revoke the token `devops vault login` stored, at the Vault that issued it, and delete it.**

Revoke the token `devops vault login` stored, at the Vault that issued it, and delete it.

The revoke goes to the address and namespace stored with the token, whatever VAULT_ADDR says
now. The local copy is deleted even when the revoke fails, for example because Vault is
unreachable or the token has expired, and the output says the revoke did not happen.

```bash
devops vault logout
```

---

## `devops vault leases`

**Inspect, renew, or revoke tracked Vault dynamic secret leases.**

Inspect, renew, or revoke tracked Vault dynamic secret leases.

Every mode needs a usable token and fails before any request without one.

```bash
devops vault leases [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--renew` | `boolean` | - | Renew every tracked lease nearing expiry |
| `--revoke` | `string` | - | Revoke a single lease by id |

---

## `devops vault audit`

**Show which provider satisfied each credential lookup in this session.**

Show which provider satisfied each credential lookup in this session.

The trail records the logical secret name and the answering provider only; secret
values are never stored or rendered.

```bash
devops vault audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Emit the audit trail as JSON |

---
