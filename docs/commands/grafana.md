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
| `--query`, `-q` | `string` | `` | Search query |

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

**Manage Grafana dashboards.**

```bash
devops grafana dashboards COMMAND [ARGS]...
```

### `devops grafana dashboards list`

**List all dashboards.**

```bash
devops grafana dashboards list
```

### `devops grafana dashboards export`

**Export a dashboard to JSON.**

```bash
devops grafana dashboards export [OPTIONS] <uid>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<uid>` | `string` | Yes | Dashboard UID |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | - |

### `devops grafana dashboards import`

**Import a dashboard from JSON.**

```bash
devops grafana dashboards import [OPTIONS] <file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file>` | `path` | Yes | Dashboard JSON file |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--folder-id` | `integer` | `0` | - |

### `devops grafana dashboards sync`

**Sync all bundled/local dashboards to Grafana.**

```bash
devops grafana dashboards sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Directory containing dashboard JSON files |

---
