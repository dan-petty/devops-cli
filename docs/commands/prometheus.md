# `devops prometheus`

Prometheus metrics querying and analysis.

## Commands

## `devops prometheus query`

**Execute an instant PromQL query.**

```bash
devops prometheus query [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--time`, `-t` | `string` | - | Evaluation timestamp for instant vector query. |

---

## `devops prometheus query-range`

**Execute a range PromQL query and summarise the result.**

```bash
devops prometheus query-range [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--start`, `-s` | `string` | `1h` | Start: duration ago (e.g. 1h) or Unix ts. |
| `--end`, `-e` | `string` | - | Query range end timestamp or relative duration. |
| `--step` | `string` | `60s` | Query resolution step interval. |

---

## `devops prometheus analyze`

**Detect anomalies and project the trend of a metric series, computed locally.**

```bash
devops prometheus analyze [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--start`, `-s` | `string` | `1h` | Start: duration ago (e.g. 1h) or Unix ts. |
| `--step` | `string` | `60s` | Query resolution step interval. |
| `--threshold`, `-t` | `float` | `3.0` | Z-score threshold before a sample is reported as anomalous. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops prometheus rules`

**List Prometheus recording and alerting rules.**

```bash
devops prometheus rules
```

---

## `devops prometheus targets`

**List active Prometheus scrape targets.**

```bash
devops prometheus targets
```

---
