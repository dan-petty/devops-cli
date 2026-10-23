# `devops openspec`

Check the OpenSpec change folders, regenerate the agent skills and archive a change.

## Commands

## `devops openspec check`

**Run the OpenSpec gate: validate every change and archived change, check the committed skills against a regeneration, render the instructions every agent reads, and find a requirement that two changes rewrite. Exits 1 on any problem.**

```bash
devops openspec check
```

---

## `devops openspec regenerate`

**Rewrite the committed OpenSpec skills with `openspec update --force` under an isolated configuration, so no developer's own profile decides what is written.**

```bash
devops openspec regenerate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops openspec archive`

**Archive a change with `openspec archive <change> --yes`, then run `openspec validate --all --strict`. Both runs use an isolated configuration with telemetry off. The command exits 1 when a run fails. A failed archive skips the validation.**

```bash
devops openspec archive [OPTIONS] <change>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<change>` | `string` | Yes | Name of the change folder under openspec/changes, as \<issue\>-\<slug\>. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
