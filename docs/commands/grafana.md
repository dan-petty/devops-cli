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
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops grafana datasources`

**List configured datasources.**

```bash
devops grafana datasources [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops grafana alerts`

**List alert rules (Grafana 9+ unified alerting).**

```bash
devops grafana alerts [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

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
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

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

With no directory, syncs the files of the environment and the product dashboard folders.
Tries every file, then exits 1 if any failed. A dashboard Grafana holds as provisioned,
such as one the dashboard sidecar loads from a ConfigMap, is skipped rather than failed.

```bash
devops grafana dashboards sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Directory of dashboard JSON files. Default: monitoring/dashboards of the environment tree, and dashboards of the product base k8s/devops when the current repository holds it. |
| `--k8s-dir` | `path` | - | The environment tree: the Kubernetes folder of the infra repo. Default: kubernetes.dir of the project profile of the current repository, else of the one infra repo that gives it. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops grafana dashboards lint`

**Statically check dashboard JSON for layout, query, and binding defects.**

Statically check dashboard JSON for layout, query, and binding defects.

Catches overlapping panels, duplicate ids, unbound datasources, malformed PromQL, and a
uid two dashboards share before a dashboard reaches Grafana, where the only symptom is a
blank, wrong, or overwritten dashboard. With no path, lints the environment and the
product dashboard folders together, so a uid that two folders share is an error too.

```bash
devops grafana dashboards lint [OPTIONS] <paths>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<paths>` | `path` | No | Dashboard JSON files or directories to lint. Default: monitoring/dashboards of the environment tree, and dashboards of the product base k8s/devops when the current repository holds it. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | - | The environment tree: the Kubernetes folder of the infra repo. Default: kubernetes.dir of the project profile of the current repository, else of the one infra repo that gives it. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---
