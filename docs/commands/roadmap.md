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
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub, print the plan and report, write nothing, and end with the GraphQL points spent and left. Migrate without a mode flag does this. |

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
| `--dry-run` | `boolean` | - | Make no request and write no file: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub and print the rendered file to stdout instead of writing it, ending with the GraphQL points spent and left. |

---

## `devops roadmap reprioritize`

**Hold the current release to its rules: after it starts only a critical fix joins it, a fix that takes it over the cap descopes one unstarted item, and Blocked, dependent, needs-split and stalled items are descoped, each with a reason comment. Once the release ships, close it, branch the next one and fill or trim it to the cap. The first run records the admitted set and moves nothing. Writes only with --confirm.**

```bash
devops roadmap reprioritize [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--confirm` | `boolean` | - | Make the changes on GitHub. Without it, reprioritize prints its plan only. |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub, print each change with its reason, write nothing, and end with the GraphQL points spent and left. Reprioritize without a mode flag does this. |

---

## `devops roadmap intake`

**Turn candidates into items: every open issue not on the board, and every board item intake left without a Priority. Each is checked for a duplicate among the board's items and the issues closed as not planned, gets a type, a priority, Value and Effort from the model with a reason comment, and goes to the backlog, or a critical fix to the release #740's admission rule allows. A candidate an agent files with --title and --body-file is labeled source/agent and held to the agent filing quota; a text that looks like it holds a secret is refused. --dry-run makes no request and prints the requests a run makes; --plan, the default, reads GitHub and calls the model, writes nothing and reports what it spent; --confirm makes the writes.**

```bash
devops roadmap intake [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--issue` | `integer` | - | Only this issue (repeatable). |
| `--title` | `string` | - | Title of a candidate that is not an issue yet; intake files it only when it is not a duplicate. Needs --body-file. |
| `--body-file` | `path` | - | File holding the new candidate's body. Needs --title. |
| `--borrow-reason` | `choice (split|follow-up)` | - | Why the new candidate may open beyond the quota's allowance: a split of an item too big for one pull request, or a follow-up a reviewer or readiness check requires. Needs --source. |
| `--source` | `string` | - | Link the new candidate came from, such as the item it splits or the review that found it; the filed body ends with it. |
| `--filed-by` | `choice (agent|person)` | `agent` | Who files the new candidate: an agent's is labeled source/agent and counts toward the quota; a person's never does. |
| `--dry-run` | `boolean` | - | Make no request, to GitHub or a model: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub and call the model, print each planned change and what the run spent, and write nothing. Intake without a mode flag does this. |
| `--confirm` | `boolean` | - | Plan as --plan does, then make the writes on GitHub. |

---

## `devops roadmap close`

**Close each item delivered to the current release, and cut the release once it holds no open item. Reads every pull request merged into release/vX.Y.Z and closes as completed each open issue a body closes with a closing keyword, commenting what changed and how it was verified (check runs and the task file's Acceptance Criteria). Once the release has no open item, one item closed as completed and no release pull request, writes docs/ROADMAP.md on chore/cut-vX.Y.Z in the clone at --root, bumps the version, pushes, and opens the release pull request into the default branch. Lists completed items with no changelog fragment. Writes only with --confirm.**

```bash
devops roadmap close [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--root` | `path` | `.` | The clone the cut runs git in (default: the current directory). |
| `--confirm` | `boolean` | - | Close the issues and make the cut. Without it, close prints its plan only. |
| `--dry-run` | `boolean` | - | Make no request and change no git ref: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub, print each issue the run closes with its comment and the cut or what holds it, write nothing, and end with the GraphQL points spent and left. Close without a mode flag does this. |

---

## `devops roadmap run`

**Run roadmap jobs that are due: evaluate due criteria across landed jobs, run due jobs in order, and record last-success execution timestamps. Without --confirm, or with --dry-run, prints the due list and runs nothing.**

```bash
devops roadmap run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--dry-run` | `boolean` | - | Make no request: print the due list of jobs and the reason each is due, and run nothing. |
| `--confirm` | `boolean` | - | Execute the due roadmap jobs. Without it, run prints the due list only. |

---
