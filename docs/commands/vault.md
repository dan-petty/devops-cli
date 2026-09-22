# `devops vault`

Enterprise HashiCorp Vault secret broker

## Commands

## `devops vault status`

**Inspect HashiCorp Vault cluster health and initialization status.**

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

**Fetch secret value from Vault or OS Keyring fallback.**

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

```bash
devops vault login [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--method`, `-m` | `string` | `approle` | Authentication method: approle or kubernetes |
| `--role` | `string` | - | Vault role name (kubernetes method) |
| `--role-id` | `string` | - | AppRole role_id |
| `--secret-id` | `string` | - | AppRole secret_id |
| `--store`, `--no-store` | `boolean` | `True` | Persist the issued token to the OS keyring |

---

## `devops vault leases`

**Inspect, renew, or revoke tracked Vault dynamic secret leases.**

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
