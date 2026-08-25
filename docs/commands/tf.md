# `devops tf`

OpenTofu and Terraform Infrastructure-as-Code operations.

## Commands

## `devops tf init`

**Initialize an OpenTofu working directory.**

```bash
devops tf init [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade`, `-u` | `boolean` | - | Upgrade modules and plugins |
| `--reconfigure` | `boolean` | - | Reconfigure backend, ignoring existing state |

---

## `devops tf plan`

**Generate and show an OpenTofu execution plan.**

```bash
devops tf plan [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--out`, `-o` | `path` | - | Write generated plan to file |
| `--destroy` | `boolean` | - | Generate a plan to destroy all resources |

---

## `devops tf apply`

**Create or update OpenTofu infrastructure.**

```bash
devops tf apply [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--plan-file`, `-p` | `path` | - | Explicit plan file to apply |
| `--auto-approve` | `boolean` | - | Skip interactive approval before applying |

---

## `devops tf destroy`

**Destroy OpenTofu-managed infrastructure.**

```bash
devops tf destroy [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--auto-approve` | `boolean` | - | Skip interactive approval before destroying |

---

## `devops tf output`

**Read an output variable from the OpenTofu state.**

```bash
devops tf output [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json`, `-j` | `boolean` | - | Output values formatted as JSON |
| `--raw`, `-r` | `boolean` | - | Output raw string without shell escapes |

---

## `devops tf validate`

**Validate the OpenTofu configuration files in a directory.**

```bash
devops tf validate [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--no-color` | `boolean` | - | Disable color codes |

---

## `devops tf fmt`

**Rewrites OpenTofu configuration files to canonical format.**

```bash
devops tf fmt [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check`, `-c` | `boolean` | - | Check formatting without writing files |
| `--recursive`, `-r` | `boolean` | `True` | Format subdirectories recursively |

---

## `devops tf status`

**Show OpenTofu directory state, initialization status, and provider plugins.**

```bash
devops tf status <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

---

## `devops tf deploy-cloud`

**Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP.**

```bash
devops tf deploy-cloud [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--provider`, `-p` | `string` | - | Target cloud provider: aws, azure, or gcp |
| `--auto-approve` | `boolean` | - | Automatically approve apply without prompt |
| `--var-file`, `-v` | `path` | - | Path to custom tfvars file |

---

## `devops tf lint`

**Run TFLint static analysis on Terraform/OpenTofu configurations.**

```bash
devops tf lint [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing Terraform / OpenTofu files |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--config`, `-c` | `path` | - | Path to .tflint.hcl config file |
| `--dry-run` | `boolean` | - | Simulate TFLint execution |
| `--json` | `boolean` | - | Output findings as JSON |

---
