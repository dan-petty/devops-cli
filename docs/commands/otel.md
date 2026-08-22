# `devops otel`

OpenTelemetry observability and tracing (alias for telemetry).

## Commands

## `devops otel status`

**Display OpenTelemetry collector endpoint, Jaeger UI URL, and connection health.**

```bash
devops otel status
```

---

## `devops otel test`

**Emit a test OpenTelemetry trace span and metric to the configured collector.**

```bash
devops otel test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | `devops-cli.manual_test` | Name for test span |

---

## `devops otel open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops otel open-ui
```

---
