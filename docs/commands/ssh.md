# `devops ssh`

Generate, rotate, audit, and register Ed25519 SSH keypairs.

## Commands

## `devops ssh generate`

**Generate a new Ed25519 SSH key with today's date suffix.**

```bash
devops ssh generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |
| `--comment`, `-c` | `string` | `` | Comment to include in public key. |

---

## `devops ssh register`

```bash
devops ssh register [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-file`, `-k` | `path` | - | Path to private key. |
| `--title` | `string` | - | Title for the item or entity. |

---

## `devops ssh rotate`

**Rotate keys older than rotation_days (default 90).**

Rotate keys older than rotation_days (default 90).

Generates, registers, and reports the old key.

```bash
devops ssh rotate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |
| `--force`, `-f` | `boolean` | - | Rotate even if not yet due. |

---

## `devops ssh list`

**List all managed SSH keys with their age and rotation status.**

```bash
devops ssh list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |

---

## `devops ssh audit`

**List all managed SSH keys with their age and rotation status.**

```bash
devops ssh audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |

---

## `devops ssh status`

**Show the active SSH key and days until rotation.**

```bash
devops ssh status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |

---
