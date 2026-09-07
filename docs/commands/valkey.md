# `devops valkey`

Valkey workstation caching and in-memory data store

## Commands

## `devops valkey ping`

**Test connection and measure round-trip latency to the Valkey server.**

```bash
devops valkey ping [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey info`

**Inspect server configuration, memory allocation, and operational metrics.**

```bash
devops valkey info [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--section`, `-s` | `string` | - | Specific INFO section (server, memory, clients, stats) |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey stats`

**Display quick diagnostic summary of server health, memory, and keys.**

```bash
devops valkey stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey keys`

**List keys matching a glob pattern.**

```bash
devops valkey keys [OPTIONS] <pattern>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pattern>` | `string` | No | Glob pattern to search for keys |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey get`

**Retrieve string value stored at key.**

```bash
devops valkey get [OPTIONS] <key>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Key to retrieve |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey set`

**Set string value of key with optional expiration TTL.**

```bash
devops valkey set [OPTIONS] <key> <value>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Key name to set |
| `<value>` | `string` | Yes | Value to associate with key |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--ex` | `integer` | - | Expiration timeout in seconds |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey flush`

**Flush and purge keys from current or all databases.**

```bash
devops valkey flush [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Flush all databases instead of just active one |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey backup`

**Trigger background RDB persistence snapshot (BGSAVE).**

```bash
devops valkey backup [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## `devops valkey cli`

**Execute raw Valkey commands directly against the server.**

```bash
devops valkey cli [OPTIONS] <command_args>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command_args>` | `string` | No | Optional command and arguments to execute directly (e.g. PING or DBSIZE) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---
