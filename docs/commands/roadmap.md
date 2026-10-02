# `devops roadmap`

Read and write the roadmap on GitHub, its source of truth: issues, milestones and the project board.

## Commands

## `devops roadmap migrate`

**Make GitHub the roadmap's source, once: bring the board in line with its template, fill unset Status, Priority, Value and Effort, retire release epics and milestones beyond the planning horizon, and record rejected roadmap ideas as issues closed as not planned. Prints the plan and a report, which lists the option renames, additions and removals a person makes in the board's field settings; writes only with --confirm, once the renames and additions are made.**

```bash
devops roadmap migrate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--confirm` | `boolean` | - | Make the planned writes to GitHub. Without it, migrate prints its plan only. |
| `--dry-run` | `boolean` | - | Print the plan and report, and write nothing. |

---

## `devops roadmap render`

**Write docs/ROADMAP.md from GitHub: the current release, the planned releases and the backlog by priority.**

```bash
devops roadmap render [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--output`, `-o` | `path` | `docs/ROADMAP.md` | File render writes. |
| `--dry-run` | `boolean` | - | Print the rendered file to stdout instead of writing it. |

---
