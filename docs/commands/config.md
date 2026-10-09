# `devops config`

Show, set, get, or initialize CLI configuration.

## Commands

## `devops config show`

**Print all configuration values, masking secrets.**

```bash
devops config show
```

---

## `devops config get`

**Print a single configuration value.**

```bash
devops config get <key>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org. |

---

## `devops config set`

**Set a configuration value. Credentials go to the OS keyring; omit VALUE to type one hidden.**

```bash
devops config set <key> <value>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org. |
| `<value>` | `string` | No | Value to set. Omit it for a credential to type it at a hidden prompt, keeping it out of the shell history and the process list. |

---

## `devops config init`

**Interactive first-time setup wizard.**

```bash
devops config init
```

---

## `devops config env-vars`

**Output environment variables available for devops-cli configuration.**

```bash
devops config env-vars [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--export`, `-e` | `boolean` | - | Print environment variables as shell export statements. |
| `--json`, `-j` | `boolean` | - | Print environment variables as JSON. |

---

## `devops config env`

**Output environment variables available for devops-cli configuration.**

```bash
devops config env [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--export`, `-e` | `boolean` | - | Print environment variables as shell export statements. |
| `--json`, `-j` | `boolean` | - | Print environment variables as JSON. |

---

## `devops config output`

**Output environment variables available for devops-cli configuration.**

```bash
devops config output [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--export`, `-e` | `boolean` | - | Print environment variables as shell export statements. |
| `--json`, `-j` | `boolean` | - | Print environment variables as JSON. |

---

## `devops config auth-headless`

**Load secret tokens into ephemeral memory for headless CI environments lacking DBus.**

```bash
devops config auth-headless <key> <token>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted secret key, e.g. grafana.token. |
| `<token>` | `string` | Yes | Secret token string. |

---

## `devops config audit-stream`

**Stream stored audit records to SIEM destination URL.**

```bash
devops config audit-stream <destination>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<destination>` | `string` | Yes | Destination Syslog or HTTP URL. |

---

## `devops config audit-keys`

**Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. Exits 1 when a config file cannot be read or parsed, reporting it unaudited.**

```bash
devops config audit-keys [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
