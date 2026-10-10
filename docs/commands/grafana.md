# `devops grafana`

Grafana dashboard and alert management.

## Commands

## `devops grafana search`

**Search Grafana dashboards and folders by query string.**

```bash
devops grafana search [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--query`, `-q` | `string` | `` | Search query. |

---

## `devops grafana datasources`

**List configured datasources.**

```bash
devops grafana datasources
```

---

## `devops grafana alerts`

**List alert rules (Grafana 9+ unified alerting).**

```bash
devops grafana alerts
```

---

## `devops grafana dashboards`

```bash
devops grafana dashboards COMMAND [ARGS]...
```

### `devops grafana dashboards list`

**List all dashboards.**

```bash
devops grafana dashboards list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops grafana dashboards export`

**Export a dashboard to JSON.**

```bash
devops grafana dashboards export [OPTIONS] <uid>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<uid>` | `string` | Yes | Dashboard UID. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Destination path for output report or artifacts. |

### `devops grafana dashboards import`

**Import a dashboard from JSON.**

```bash
devops grafana dashboards import [OPTIONS] <file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file>` | `path` | Yes | Path to dashboard JSON file to import. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--folder-id` | `integer` | `0` | Target Grafana folder ID for dashboard import. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops grafana dashboards sync`

**Sync every dashboard JSON file in a directory to Grafana.**

Sync every dashboard JSON file in a directory to Grafana.

Tries every file, then exits 1 if any failed. A dashboard Grafana holds as provisioned,
such as one the dashboard sidecar loads from a ConfigMap, is skipped rather than failed.

```bash
devops grafana dashboards sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Directory path containing dashboard definitions. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops grafana dashboards lint`

**Statically check dashboard JSON for layout, query, and binding defects.**

Statically check dashboard JSON for layout, query, and binding defects.

Catches overlapping panels, duplicate ids, unbound datasources, malformed PromQL, and a
uid two dashboards share before a dashboard reaches Grafana, where the only symptom is a
blank, wrong, or overwritten dashboard.

```bash
devops grafana dashboards lint [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Dashboard JSON file or directory to lint. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
