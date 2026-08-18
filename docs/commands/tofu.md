# `devops tofu`

OpenTofu and Terraform Infrastructure-as-Code operations (alias for tf).

## Commands

## `devops tofu init`

**Initialize an OpenTofu working directory.**

```bash
devops tofu init [OPTIONS] <directory>
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

## `devops tofu plan`

**Generate and show an OpenTofu execution plan.**

```bash
devops tofu plan [OPTIONS] <directory>
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

## `devops tofu apply`

**Create or update OpenTofu infrastructure.**

```bash
devops tofu apply [OPTIONS] <directory>
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

## `devops tofu destroy`

**Destroy OpenTofu-managed infrastructure.**

```bash
devops tofu destroy [OPTIONS] <directory>
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

## `devops tofu output`

**Read an output variable from the OpenTofu state.**

```bash
devops tofu output [OPTIONS] <directory>
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

## `devops tofu validate`

**Validate the OpenTofu configuration files in a directory.**

```bash
devops tofu validate [OPTIONS] <directory>
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

## `devops tofu fmt`

**Rewrites OpenTofu configuration files to canonical format.**

```bash
devops tofu fmt [OPTIONS] <directory>
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

## `devops tofu status`

**Show OpenTofu directory state, initialization status, and provider plugins.**

```bash
devops tofu status <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

---

## `devops tofu deploy-cloud`

**Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP.**

```bash
devops tofu deploy-cloud [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--provider`, `-p` | `string` | - | Target cloud provider: aws, azure, or gcp |
| `--auto-approve` | `boolean` | - | Automatically approve apply without prompt |
| `--var-file`, `-v` | `path` | - | Path to custom tfvars file |

---
