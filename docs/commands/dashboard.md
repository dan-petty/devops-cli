# `devops dashboard`

Interactive terminal UI dashboard for workstation situational awareness.

## Commands

## `devops dashboard`

**Interactive terminal UI dashboard for workstation situational awareness.**

```bash
devops dashboard [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--summary`, `-s` | `boolean` | - | Print static summary panels and exit instead of starting full-screen TUI. |
| `--refresh-interval`, `-r` | `integer` | `5` | Auto-refresh interval in seconds for live dashboard updates. |
| `--tab`, `-t` | `string` | `k8s` | Initial tab to activate (1=k8s, 2=docker, 3=telemetry, 4=ai, 5=valkey). |
| `--dry-run` | `boolean` | - | Simulate dashboard launch and print static summary. |

---
