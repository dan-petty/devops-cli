# `devops openspec`

Check and regenerate the OpenSpec change folders and agent skills.

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
