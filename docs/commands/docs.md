# `devops docs`

Generate and validate CLI and API documentation.

## Commands

## `devops docs generate`

**Generate comprehensive Markdown or JSON documentation for all CLI commands and tools.**

```bash
devops docs generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Target directory for generated documentation files (default: docs/). |
| `--format`, `-f` | `string` | `markdown` | Documentation output format ('markdown' or 'json'). |
| `--sync-readme`, `--no-sync-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |
| `--check` | `boolean` | - | Validate that existing documentation is up to date without writing files. |

---

## `devops docs check`

**Check that generated documentation and README.md are up to date with codebase.**

```bash
devops docs check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Directory containing documentation to check (default: docs/). |
| `--check-readme`, `--no-check-readme` | `boolean` | `True` | Verify README.md Command Matrix synchronization as well. |

---

## `devops docs sync-readme`

**Synchronize the Complete Command Matrix table in README.md with live CLI commands.**

```bash
devops docs sync-readme [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--readme-path`, `-r` | `path` | - | Path to README.md file (default: workspace root README.md). |
| `--check` | `boolean` | - | Verify README.md table is synchronized without writing changes. |

---
