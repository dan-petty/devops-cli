# `devops roadmap`

Read and write the roadmap on GitHub, its source of truth: issues, milestones and the project board.

## Commands

## `devops roadmap intake`

**Turn candidates into items: every open issue not on the board, and every board item intake left without a Priority. The model compares each with the board's items and the issues closed as not planned, but not with an issue that has sub-issues, because its sub-issues deliver it. It names a possible duplicate for a person to close: intake never closes an issue and never drops a candidate. Each gets a type, a priority, Value and Effort from the model with a reason comment, and goes to the backlog. Intake sets no milestone: a person plans the milestones on the board, and a milestone an issue has stays. An open issue whose board card a person archived is a candidate too: intake restores the card, which keeps its values and milestone; close the issue as not planned to keep it off the roadmap. A candidate an agent files with --title and --body-file is labeled source/agent, and intake files it, a possible duplicate too, unless a run that stopped after filing left an open issue with its title and body, which intake then places; a text that looks like it holds a secret is refused. --dry-run makes no request and prints the requests a run makes; --plan, the default, reads GitHub and calls the model, writes nothing and reports what it spent; --confirm makes the writes.**

```bash
devops roadmap intake [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml at (default: the repository's default branch). |
| `--issue` | `integer` | - | Only this issue (repeatable). |
| `--title` | `string` | - | Title of a candidate that is not an issue yet; intake files it, and names a possible duplicate for a person to close. Needs --body-file. |
| `--body-file` | `path` | - | File holding the new candidate's body. Needs --title. |
| `--source` | `string` | - | Link the new candidate came from, such as the item it splits or the review that found it; the filed body ends with it. Intake never names the issue that this link names, or a sub-issue of that issue, as a possible duplicate of the candidate. |
| `--filed-by` | `choice (agent|person)` | `agent` | Who files the new candidate: an agent's is labeled source/agent; a person's is not. |
| `--limit` | `integer` | - | Decide at most this many candidates, the oldest first, and leave the rest for a later run. Without it, intake decides every candidate. It keeps no record of what it decided; the intake that devops roadmap run and the Service run keeps one, so a candidate it left undecided waits behind the fresh ones. |
| `--dry-run` | `boolean` | - | Make no request, to GitHub or a model: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub and call the model, print each planned change and what the run spent, and write nothing. Intake without a mode flag does this. |
| `--confirm` | `boolean` | - | Plan as --plan does, then make the writes on GitHub. |

---

## `devops roadmap refine`

**Refine roadmap items to Ready with proposed design, tasks, and acceptance criteria, using code, documentation, and external research. Without --item, refine takes items nearest place first: each open milestone's New items, by due date and then by number, then the backlog's P0 and P1 items, then the backlog's other New items, each place by priority. Only --limit stops a run. The number of Ready items does not stop it. In each open milestone and among the backlog's P0 and P1 items it also takes Ready items it has no record of, and sets one back to New when it finds it not ready. An item refine cannot set to Ready gets one comment with its next step. The step is the questions a person answers, the split a person makes, or the open items it waits on. Refine looks at the item again after a reply, a body edit or the close of those items, or after a commit on the default branch changes a file that the block cites. The report groups every item by its next step. An item whose model call fails is skipped and reported; the others are still refined, and refine then exits 1.**

```bash
devops roadmap refine [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml at (default: the repository's default branch). |
| `--source` | `path` | `.` | Path to the repository checkout (defaults to current directory). |
| `--item` | `integer` | - | Specific issue number to refine instead of selecting by priority. Refine refines it when it is open and New or Ready, even when nothing changed since its last round. |
| `--limit` | `integer` | `3` | Maximum number of items to refine in this run (default 3). |
| `--dry-run` | `boolean` | - | Make no request and change no git ref: print what refine would plan and run, with placeholders. |
| `--confirm` | `boolean` | - | Refine the items and write the proposed designs to GitHub. Without it, refine prints its plan only. |

---

## `devops roadmap run`

**Run the roadmap jobs that are due, in order: metrics, then intake and refine, and record each one's last success. Intake is due on an issue reopened, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every hour, on a first run, and after an intake that placed a critical fix or a P0 item. Without --confirm, or with --dry-run, prints the due list and runs nothing.**

```bash
devops roadmap run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml at (default: the repository's default branch). |
| `--dry-run` | `boolean` | - | Make no request: print the due list of jobs and the reason each is due, and run nothing. |
| `--confirm` | `boolean` | - | Execute the due roadmap jobs. Without it, run prints the due list only. |

---

## `devops roadmap return`

**Return an item to New on the roadmap board with an evidence comment, handing it back to refinement when it cannot be built as specified or needs a refactor beyond its scope.**

```bash
devops roadmap return [OPTIONS] <item>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<item>` | `integer` | Yes | The issue or item number to return to New. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--comment`, `-c` | `string` | `` | Evidence comment explaining why the item cannot be built as specified. |
| `--comment-file` | `path` | - | Path to file containing the evidence comment. |
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml at (default: the repository's default branch). |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--confirm` | `boolean` | - | Make the writes to GitHub (post comment and set Status to New). |

---
