# `devops telemetry`

OpenTelemetry tracing, metrics, and Jaeger observability.

## Commands

## `devops telemetry status`

**Check OpenTelemetry collector health, Jaeger endpoint, and trace propagation status.**

```bash
devops telemetry status
```

---

## `devops telemetry test`

**Emit a test OpenTelemetry trace span and metric to the configured collector.**

```bash
devops telemetry test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | `devops-cli.manual_test` | Name for test span. |

---

## `devops telemetry profile`

**Display terminal-rendered waterfall breakdown and latency heatmap of OpenTelemetry spans.**

```bash
devops telemetry profile [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | No | CLI command string to profile and render waterfall for (e.g. 'devops k8s contexts'). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--trace-id`, `-t` | `string` | - | Specific trace ID to visualize from in-memory span buffer. |
| `--last`, `-l` | `boolean` | - | Render waterfall for the most recently executed command trace. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops telemetry open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops telemetry open-ui
```

---
