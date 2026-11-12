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
| `--sync-readme` / `--no-sync-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |
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
| `--check-readme` / `--no-check-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |

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

## `devops docs site`

```bash
devops docs site COMMAND [ARGS]...
```

### `devops docs site build`

**Stage docs/ and the root documents in .data/site-src/, change each link to a repository file outside the site into a GitHub link at the build commit, and build the site with Zensical into .data/site-src/site/. Each page shows the version, the commit and the build time. The page is docs/SDLC.md.**

```bash
devops docs site build [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--strict` | `boolean` | - | Fail on a Zensical warning, such as a link to a missing page or anchor, and on a page that no nav tab lists. |
| `--serve` | `boolean` | - | Build and serve the staged site on localhost:8000. Run the command again after a change to a page. |
| `--root`, `-r` | `path` | `.` | Repository root that holds zensical.toml (default: the current directory). |

---
