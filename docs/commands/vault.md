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
