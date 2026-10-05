# `devops status`

Inspect published operational status of upstream platforms (GitHub, Cloudflare)

## Commands

## `devops status`

**Inspect published operational status of upstream cloud platforms (GitHub, Cloudflare)**

```bash
devops status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--service`, `-s` | `string` | `all` | Target service to inspect (all, github, cloudflare) |
| `--json`, `-j` | `boolean` | - | Output status details in JSON format |
| `--emit-telemetry` | `boolean` | - | Emit operational service status metrics over OpenTelemetry to Prometheus |

---
