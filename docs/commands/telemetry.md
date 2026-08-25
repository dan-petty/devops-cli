# `devops telemetry`

OpenTelemetry observability, tracing, and metrics management.

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
| `--name`, `-n` | `string` | `devops-cli.manual_test` | Name for test span |

---

## `devops telemetry open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops telemetry open-ui
```

---
