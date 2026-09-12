# `devops sandbox`

Isolated workload sandbox container lifecycle engine.

## Commands

## `devops sandbox deploy`

**Deploy an isolated background container sandbox with security containment.**

```bash
devops sandbox deploy [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | No | Optional container command |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--image`, `-i` | `string` | `python:3.14-slim` | Container image for the sandbox workload. |
| `--name`, `-n` | `string` | - | Friendly identifier name for the sandbox instance. |
| `--port`, `-p` | `integer` | - | Container port(s) to dynamically expose on available host ports. |
| `--workspace`, `-w` | `path` | `.` | Host workspace path to mount into container /workspace. |
| `--memory`, `-m` | `string` | `2g` | Memory limit for the container (e.g. 512m, 2g). |
| `--cpus`, `-c` | `float` | `2.0` | CPU quota limit for the container (e.g. 1.0, 2.0). |
| `--read-only`, `--no-read-only` | `boolean` | `True` | Mount root filesystem as read-only with a tmpfs /tmp. |
| `--network` | `string` | `bridge` | Docker network mode (bridge | host | none). |
| `--env`, `-e` | `string` | - | Environment variable in KEY=VALUE format. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops sandbox status`

**Inspect status of deployed sandbox containers.**

```bash
devops sandbox status [OPTIONS] <instance_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<instance_id>` | `string` | No | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Apply operation across all registered sandbox instances. |
| `--json` | `boolean` | - | Output details in structured JSON format. |

---

## `devops sandbox stop`

**Gracefully stop and tear down a sandbox container.**

```bash
devops sandbox stop [OPTIONS] <instance_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<instance_id>` | `string` | No | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Apply operation across all registered sandbox instances. |
| `--timeout`, `-t` | `integer` | `10` | Graceful stop timeout in seconds before SIGKILL. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops sandbox exec`

**Execute a command inside an active sandbox container.**

```bash
devops sandbox exec [OPTIONS] <instance_id> <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<instance_id>` | `string` | Yes | Unique instance ID or name of the sandbox. |
| `<command>` | `string` | Yes | Command and arguments to execute inside sandbox |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workdir`, `-w` | `string` | - | Working directory inside the container for command execution. |

---
