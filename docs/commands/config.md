# `devops config`

Show, set, get, or initialize CLI configuration.

## Commands

## `devops config show`

**Print every setting that a variable sets and every credential. A credential shows as set or not set, never its value.**

```bash
devops config show [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

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

Set a configuration value. Credentials go to the OS keyring; omit VALUE to type one hidden.

A multi-line credential, such as a PEM private key, comes from a file or stdin:
`devops config set <key> --from-file key.pem`, or `--from-file -` to read stdin.

```bash
devops config set [OPTIONS] <key> <value>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org. |
| `<value>` | `string` | No | Value to set. Omit it for a credential to type it at a hidden prompt, keeping it out of the shell history and the process list. The prompt reads one line, so a multi-line credential comes from --from-file. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--from-file` | `filename` | - | Read the credential from this file, or from stdin to its end when the path is -. Every line and the last newline stay as the input has them, and the value never shows in the output. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops config unset`

**Remove a key from the config file, also a key that stops the settings from loading.**

Remove a key from the config file, also a key that stops the settings from loading.

The command edits the active config file and loads no settings. To edit another file, set
`DEVOPS_CLI_CONFIG` to its path for the command. It keeps the other lines and comments, and
it copies the file to `<name>.bak-<YYYYMMDD-HHMMSS>` before the change. In that copy, and in
each older copy, a credential that the command removes shows as `***REDACTED***`, so no copy
holds its value. A key that the file does not hold exits 1. A credential in the OS keyring
stays. Store a credential before you remove it, with `devops config set <key>`, or with
`--from-file <path>` for a multi-line one.

```bash
devops config unset <key>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org. |

---

## `devops config init`

**Interactive first-time setup wizard.**

```bash
devops config init [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

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
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
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
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
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
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
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

**Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. The audit scans each config file that the settings merge: the global config file and the project config file. It also scans config.yaml and .devops/config.yaml in the current directory. Exits 0 only when the audit is compliant. Exits 1 when a config file holds a plaintext secret, or when a config file cannot be read or parsed, reporting it unaudited. The full report prints before the exit. The alert of a leak names two commands. `devops config set <key>` stores a credential in the keyring. Add `--from-file <path>` for a multi-line credential, such as a PEM key. `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` removes the value from the file of the leak.**

```bash
devops config audit-keys [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---
