# `devops test`

Test suite orchestration, git-diff aware test selector, and load testing.

## Commands

## `devops test run`

**Execute pytest test suite with optional git-diff aware test selection.**

```bash
devops test run [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target test file or test directory. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--changed`, `-c` | `boolean` | - | Run only tests related to files modified in git working tree or current branch. |
| `--cov` | `boolean` | - | Run with code coverage analysis. |
| `--fail-fast`, `-x` | `boolean` | - | Stop immediately on the first test failure. |
| `--verbose`, `-v` | `boolean` | - | Enable verbose pytest output (-vv). |
| `-k` | `string` | - | Filter tests by expression. |
| `--dry-run` | `boolean` | - | Simulate test execution. |

---

## `devops test load`

**Execute developer-centric load, spike, and latency tests against services using k6.**

```bash
devops test load [OPTIONS] <script_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<script_path>` | `path` | No | Path to k6 JavaScript test script or endpoint definition. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--vus`, `-u` | `integer` | `10` | Number of concurrent virtual users (VUs). |
| `--duration`, `-d` | `string` | `30s` | Test execution duration (e.g. 30s, 1m). |
| `--summary-export`, `-s` | `path` | - | Path to export JSON summary metrics. |
| `--dry-run` | `boolean` | - | Simulate test execution. |

---
