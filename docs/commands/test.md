# `devops test`

Performance, smoke, and load testing.

## Commands

## `devops test`

**Execute developer-centric load, spike, and latency tests against services using k6.**

```bash
devops test [OPTIONS] <script_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<script_path>` | `path` | No | Path to k6 JavaScript test script or endpoint definition |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--vus`, `-u` | `integer` | `10` | Number of concurrent virtual users (VUs) |
| `--duration`, `-d` | `string` | `30s` | Test execution duration (e.g. 30s, 1m) |
| `--summary-export`, `-s` | `path` | - | Path to export JSON summary metrics |
| `--dry-run` | `boolean` | - | Simulate load test execution |

---
