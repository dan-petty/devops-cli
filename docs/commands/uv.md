# `devops uv`

uv dependency management proxies.

## Commands

## `devops uv sync`

**Sync project dependencies into the virtual environment.**

```bash
devops uv sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--frozen` | `boolean` | - | Do not update lockfile. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops uv lock`

**Regenerate the uv lockfile.**

```bash
devops uv lock [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade` | `boolean` | - | Upgrade dependencies while locking. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops uv python-install`

**Install project Python version with uv.**

```bash
devops uv python-install [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Python version to install (defaults to .python-version). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops uv run`

**Run an arbitrary command using `uv run`.**

Run an arbitrary command using `uv run`.

Example:
  devops uv run -- pytest -q

A dry run lists the one `uv run` command and starts nothing. What that command does is
not a request of devops-cli, so the plan does not list it.

```bash
devops uv run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
