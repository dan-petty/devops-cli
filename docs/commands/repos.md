# `devops repos`

Clone, synchronize, and manage organization repositories.

## Commands

## `devops repos clone-org`

**Clone all repos from a GitHub org into repos/<org>/.**

```bash
devops repos clone-org [OPTIONS] <org>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<org>` | `string` | No | GitHub organisation name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--private`, `--no-private` | `boolean` | `True` | - |
| `--forks`, `--no-forks` | `boolean` | - | - |

---

## `devops repos clone`

**Clone an individual repository into repos/_standalone/<name>/.**

```bash
devops repos clone [OPTIONS] <url>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<url>` | `string` | Yes | Repository URL (SSH or HTTPS). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |

---

## `devops repos list`

**List all cloned repositories.**

```bash
devops repos list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

---

## `devops repos update`

**Fetch (and optionally pull) all tracking branches across repos.**

```bash
devops repos update [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull`, `--no-pull` | `boolean` | `True` | - |

---

## `devops repos sync`

**Fetch (and optionally pull) all tracking branches across repos.**

```bash
devops repos sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull`, `--no-pull` | `boolean` | `True` | - |

---
