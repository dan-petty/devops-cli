# `devops telemetry`

OpenTelemetry tracing, metrics, and Jaeger observability.

## Commands

## `devops telemetry status`

**Check OpenTelemetry collector health, Jaeger endpoint, and trace propagation status.**

```bash
devops telemetry status
```

---

## `devops telemetry connect`

**Find the cluster's OpenTelemetry collector, check it answers, and send telemetry there.**

```bash
devops telemetry connect [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context` | `string` | - | Kubernetes context of the cluster running the collector (default: current). |
| `--namespace`, `-n` | `string` | `otel` | Namespace of the collector service. |
| `--service` | `string` | `otel-collector-opentelemetry-collector` | Name of the collector service. |
| `--save`, `--no-save` | `boolean` | `True` | Save the endpoint as telemetry.endpoint (default) or only check it. |

---

## `devops telemetry logfire`

**Display Logfire structured observability bridge status and token metrics.**

```bash
devops telemetry logfire [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

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
| `--logfire` | `boolean` | - | Emit test span via Logfire bridge. |

---

## `devops telemetry profile`

**Run a command, or name a trace, and show its span waterfall as Jaeger recorded it.**

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
| `--trace-id`, `-t` | `string` | - | Trace ID to read from Jaeger and show, instead of running a command. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops telemetry open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops telemetry open-ui
```

---

## `devops telemetry semconv`

**The GenAI semantic conventions that LLM span attributes are checked against.**

```bash
devops telemetry semconv COMMAND [ARGS]...
```

### `devops telemetry semconv refresh`

**Resolve the GenAI semantic conventions at a commit with weaver and rewrite the snapshot.**

```bash
devops telemetry semconv refresh [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--commit` | `string` | - | Full 40-character commit SHA of open-telemetry/semantic-conventions-genai to resolve. |

---
