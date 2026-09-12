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
| `--read-only` | `boolean` | `True` | Mount root filesystem as read-only with a tmpfs /tmp. |
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

## `devops sandbox probe`

**Probe endpoint readiness and service health across network protocols.**

```bash
devops sandbox probe [OPTIONS] <identifier>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<identifier>` | `string` | Yes | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--protocol`, `-p` | `string` | - | Network protocol(s) to probe (tcp, http, openapi, grpc). |
| `--path` | `string` | - | HTTP request path(s) to probe for readiness. |
| `--expected-status` | `string` | - | Expected HTTP response status code(s). |
| `--regex`, `-r` | `string` | - | Regex pattern to assert against HTTP response body. |
| `--latency-sla` | `float` | - | Maximum acceptable response latency budget in milliseconds. |
| `--timeout`, `-t` | `float` | `5.0` | Graceful stop timeout in seconds before SIGKILL. |
| `--json` | `boolean` | - | Output details in structured JSON format. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops sandbox metrics`

**Capture real-time cgroup v2 metrics and scrape Prometheus application metrics.**

```bash
devops sandbox metrics [OPTIONS] <identifier>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<identifier>` | `string` | Yes | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prom-endpoint`, `-p`, `--path` | `string` | `/metrics` | Prometheus metrics scrape path (default /metrics). |
| `--timeout`, `-t` | `float` | `5.0` | HTTP timeout in seconds for Prometheus metrics scraping (default: 5.0). |
| `--warn-memory-pct` | `float` | `80.0` | Warning threshold percentage for container memory consumption. |
| `--warn-cpu-pct` | `float` | `85.0` | Warning threshold percentage for container CPU utilization. |
| `--latency-sla-ms` | `float` | - | Maximum acceptable average HTTP request latency SLA in milliseconds (disabled by default). |
| `--json` | `boolean` | - | Output details in structured JSON format. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops sandbox traces`

**Visualize distributed trace waterfall and cross-service latency for sandbox workloads.**

```bash
devops sandbox traces [OPTIONS] <identifier>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<identifier>` | `string` | No | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--trace-id`, `-t` | `string` | - | Specific OpenTelemetry trace ID to retrieve and visualize. |
| `--last`, `-l` | `boolean` | - | Visualize spans for the most recently executed trace. |
| `--probe` | `boolean` | - | Execute an endpoint health probe before visualizing the resulting trace. |
| `--jaeger-url` | `string` | - | Override Jaeger Query HTTP endpoint (default: http://localhost:16686). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
