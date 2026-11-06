# `devops new`

Write the files of a new command or a new test in project form.

## Commands

## `devops new command`

**Add a command to a group that exists: its function, its help and message entries, and a failing test. The command writes over no file and prints the steps that stay manual. The page of the group is docs/commands/\<group\>.md.**

```bash
devops new command [OPTIONS] <group> <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<group>` | `string` | Yes | Name of the group module under src/devops_cli/commands. |
| `<name>` | `string` | Yes | Name of the new command, in lower case with hyphens. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops new test`

**Write the test file of a module of src/devops_cli at its mirror path under tests, with the fixtures of the edges the module reaches. The command writes over no file. The page is docs/TESTING.md.**

```bash
devops new test [OPTIONS] <module>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<module>` | `string` | Yes | Path of the source module, such as src/devops_cli/config/constants.py. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
