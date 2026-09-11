# `devops docs`

Generate and validate CLI and architecture documentation.

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
| `--format`, `-f` | `string` | `markdown` | Output format type (table, json, yaml, markdown). |
| `--sync-readme`, `--no-sync-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |
| `--check` | `boolean` | - | Verify that documentation is strictly up to date with CLI code. |

---

## `devops docs check`

**Check that generated documentation and README.md are up to date with codebase.**

```bash
devops docs check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Target directory for generated documentation files (default: docs/). |
| `--check-readme`, `--no-check-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |

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
| `--check` | `boolean` | - | Verify that documentation is strictly up to date with CLI code. |

---

## `devops docs compact`

**Compact historical documentation for completed release series.**

```bash
devops docs compact [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--series`, `-s` | `string` | `v0.2` | Release series prefix to compact (e.g., 'v0.2', 'v0.1'). |
| `--docs-dir`, `-d` | `path` | - | Path to repository docs/ directory (default: docs/). |
| `--archive-dir`, `-a` | `path` | - | Path to historical archive directory (default: docs/agent/archive/). |
| `--check` | `boolean` | - | Check if documentation compaction would make changes without modifying files. |
| `--roadmap-only` | `boolean` | - | Only compact docs/ROADMAP.md. |
| `--release-notes-only` | `boolean` | - | Only compact docs/RELEASE_NOTES.md. |
| `--log-only` | `boolean` | - | Only compact docs/LOG.md. |
| `--dry-run` | `boolean` | - | Show debug output of commands and AI requests without executing delegated subcommands or external write actions. |

---
