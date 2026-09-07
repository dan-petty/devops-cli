# `devops gh`

GitHub Views, Projects, Milestones, and Labels automation.

## Commands

## `devops gh labels`

```bash
devops gh labels COMMAND [ARGS]...
```

### `devops gh labels list`

**List all labels defined in the remote repository.**

```bash
devops gh labels list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh labels sync`

**Synchronize repository labels against the declarative YAML schema.**

```bash
devops gh labels sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--file`, `-f` | `path` | `.github/labels.yml` | Path to declarative labels.yml file |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` | `boolean` | - | Preview label reconciliation without making changes |

### `devops gh labels audit`

**Audit open pull requests for mandatory type/ and scope/ taxonomy labels.**

```bash
devops gh labels audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh milestones`

```bash
devops gh milestones COMMAND [ARGS]...
```

### `devops gh milestones list`

**List repository milestones and track issue completion rates.**

```bash
devops gh milestones list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `all` | Milestone state filter |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh milestones sync`

**Extract release milestones from ROADMAP.md and sync to repository.**

```bash
devops gh milestones sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--roadmap`, `-r` | `path` | `docs/ROADMAP.md` | Path to docs/ROADMAP.md file |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` | `boolean` | - | Simulate milestone extraction without creating remote records |

### `devops gh milestones status`

**Inspect detailed progress and issue health for a specific milestone.**

```bash
devops gh milestones status [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Milestone version or title (e.g. v0.2.11) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh milestones close`

**Close a repository release milestone by title or version.**

```bash
devops gh milestones close [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Milestone version or title (e.g. v0.2.11) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh project`

```bash
devops gh project COMMAND [ARGS]...
```

### `devops gh project status`

**Inspect the declarative GitHub Projects v2 template structure and views.**

```bash
devops gh project status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

### `devops gh project sync`

**Sync task items from task.md into GitHub Projects status.**

```bash
devops gh project sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--task-file`, `-f` | `path` | `docs/agent/task.md` | Path to docs/agent/task.md |
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run`, `--no-dry-run` | `boolean` | - | Preview task card items without remote mutations |

### `devops gh project link`

**Link a GitHub Project v2 board to the repository.**

```bash
devops gh project link [OPTIONS] <project_number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<project_number>` | `integer` | Yes | GitHub Projects v2 board number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh project template`

**Display the raw GitHub Projects v2 declarative JSON template.**

```bash
devops gh project template [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

---

## `devops gh views`

```bash
devops gh views COMMAND [ARGS]...
```

### `devops gh views list`

**List all standardized GitHub Projects v2 views configured for this workspace.**

```bash
devops gh views list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

### `devops gh views spec`

**Output JSON schema specification for all configured project views.**

```bash
devops gh views spec [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

### `devops gh views sync`

**Synchronize standardized views with the remote GitHub Projects v2 board.**

```bash
devops gh views sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |
| `--repo`, `-R` | `string` | - | Target repository |

---
