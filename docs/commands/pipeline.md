# `devops pipeline`

Programmable containerized pipeline execution (Dagger).

## Commands

## `devops pipeline`

**Execute reproducible, containerized developer pipelines with Dagger.**

```bash
devops pipeline [OPTIONS] <pipeline_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pipeline_path>` | `path` | No | Path to Dagger module directory or pipeline script |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--function`, `-f` | `string` | - | Target pipeline function to call |
| `--args`, `-a` | `string` | - | Arguments to forward to the pipeline execution |
| `--dry-run` | `boolean` | - | Simulate pipeline execution |

---
