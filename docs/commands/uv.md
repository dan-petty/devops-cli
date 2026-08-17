# `devops uv`

Run uv commands through devops.

## Commands

## `devops uv sync`

**Sync project dependencies into the virtual environment.**

```bash
devops uv sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--frozen` | `boolean` | - | Do not update lockfile |

---

## `devops uv lock`

**Regenerate the uv lockfile.**

```bash
devops uv lock [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade` | `boolean` | - | Upgrade dependencies while locking |

---

## `devops uv python-install`

**Install project Python version with uv.**

```bash
devops uv python-install [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Python version to install (defaults to .python-version) |

---

## `devops uv run`

**Run an arbitrary command using `uv run`.**

Run an arbitrary command using `uv run`.

Example:
  devops uv run -- pytest -q

```bash
devops uv run
```

---
