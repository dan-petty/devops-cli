# `devops roadmap`

Read and write the roadmap on GitHub, its source of truth: issues, their labels and milestones.

## Commands

## `devops roadmap intake`

**Turn each open issue with no priority label into a roadmap item, or file a new candidate: intake sets the labels, adds a reason comment and names a possible duplicate for a person to close. It writes nothing without --confirm. Details: docs/roadmap/intake.md.**

```bash
devops roadmap intake [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/labels.yml at (default: the repository's default branch). |
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

**Refine roadmap items to Ready: investigate open questions with tools that read the code and the documentation, then write the design, tasks and acceptance criteria to GitHub. Without --confirm, refine prints its plan only. Details: docs/roadmap/refine.md.**

```bash
devops roadmap refine [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--source` | `path` | `.` | Path to the repository checkout (defaults to current directory). |
| `--item` | `integer` | - | Specific issue number to refine instead of selecting by priority. Refine refines it when it is open and New or Ready, even when nothing changed since its last round, whoever opened it, and however many comments refine wrote on it. |
| `--limit` | `integer` | `3` | Maximum number of items to refine in this run (default 3). |
| `--dry-run` | `boolean` | - | Make no request and change no git ref: print what refine would plan and run, with placeholders. |
| `--confirm` | `boolean` | - | Refine the items and write the proposed designs to GitHub. Without it, refine prints its plan only. |

---

## `devops roadmap alternatives`

**Check open items for an open, maintained tool or library that already covers their need. A check posts one comment and a body block, and a person decides what the tool means for the item. Details: docs/roadmap/alternatives.md.**

```bash
devops roadmap alternatives [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--item` | `integer` | - | Specific issue number to check instead of selecting. Alternatives checks it when it is open, whoever opened it and whatever its status, even when its check is current. |
| `--limit` | `integer` | - | Maximum number of items to check in this run (default: roadmap.alternatives.first_pass_limit, 20, while an item has no check, and roadmap.alternatives.limit, 5, after). |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, with placeholders. |
| `--plan` | `boolean` | - | Run the checks and print them, and write nothing. This is the default. |
| `--confirm` | `boolean` | - | Write each check to GitHub: its comment, its body block and its job record. |

---

## `devops roadmap retitle`

**Shorten the title summary of open items that is over 60 characters. The job keeps the type and the scope. A Planned item takes the summary of its plan pull request title and needs no model call; another item gets one model call. The job leaves a title that a person changed after the last job comment. Without --confirm, it prints the new titles and writes nothing.**

```bash
devops roadmap retitle [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--item` | `integer` | - | Specific issue number to examine instead of selecting. Retitle examines it when it is open and its title summary is over the limit. |
| `--limit` | `integer` | - | Maximum number of items to examine in this run (default: 25). The lowest numbers go first. |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, with placeholders. |
| `--confirm` | `boolean` | - | Write each new title to GitHub, and a comment on the item. |

---

## `devops roadmap stage`

**Make Ready items Staged: for each item, push a branch with its OpenSpec change in one commit and open a draft plan pull request. The Service marks the draft ready when its checks pass. Details: docs/roadmap/stage.md.**

```bash
devops roadmap stage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--source` | `path` | - | Path to a clone of the repository at its default branch. Without it, the job clones the repository into its own model clone, updates it, and uses it. |
| `--item` | `integer` | - | Stage the one issue this number names, when it is open and Ready, and ignore the filter and the limit. |
| `--filter` | `string` | - | A label filter in the form family=value, over the families status, priority, type, value and effort. Repeat the option: the values of one family are alternatives, and the families all apply. The default is the setting roadmap.stage.filter. |
| `--limit` | `integer` | - | Maximum number of items to stage in this run. The default is the setting roadmap.stage.limit. |
| `--step-tokens` | `integer` | - | Most tokens that the inputs of one implementation step may hold. The default is the setting roadmap.stage.step_tokens. |
| `--dry-run` | `boolean` | - | Make no request: print the requests and the git commands that a run makes, with placeholders. |
| `--plan` | `boolean` | - | Read GitHub and call the model, and write nothing: print the changes that --confirm writes. This is the mode when no flag is given. |
| `--confirm` | `boolean` | - | Plan as --plan does, then make the writes in git and on GitHub. |
| `--why` | `boolean` | - | Also list the open items that the filter does not name, each with the family it misses, under 'Matched no filter'. Without it, the plan does not list them. |

---

## `devops roadmap run`

**Run the roadmap jobs that are due, in order: metrics, then intake, refine and the alternatives check, and record each one's last success. Intake is due on an issue reopened, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every 31 minutes, on a first run, and after an intake that placed a critical fix or a P0 item; retitle is due every 61 minutes and on a first run; the alternatives check is due every 719 minutes and on a first run, and checks at most roadmap.alternatives.first_pass_limit items while an item has no check, and roadmap.alternatives.limit items after. Without --confirm, or with --dry-run, prints the due list and runs nothing.**

```bash
devops roadmap run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--dry-run` | `boolean` | - | Make no request: print the due list of jobs and the reason each is due, and run nothing. |
| `--confirm` | `boolean` | - | Execute the due roadmap jobs. Without it, run prints the due list only. |

---

## `devops roadmap implement`

**Implement a Staged or Planned item in bounded steps: with --group, run one task group in a checkout; without it, run the job, which takes items, runs their steps, and marks the pull request ready. Details: docs/roadmap/implement.md.**

```bash
devops roadmap implement [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--source` | `path` | - | Path to a git checkout. For a step it holds the change (default: the current directory). For the job it is a clone of the repository (default: the model clone). |
| `--item` | `integer` | - | The issue number of an item. With --group, the item whose change holds the group. Without it, the one item the job takes when it is Staged or Planned, ignoring the filter and the limit. |
| `--group` | `integer` | - | Run this one task group (the number in the tasks.md of the change) as a step, and not the job. |
| `--filter` | `string` | - | A label filter for the job, in the form family=value, over the families status, priority, type, value and effort. Repeat the option: the values of one family are alternatives, and the families all apply. |
| `--limit` | `integer` | `1` | Maximum number of items the job takes in this run (default 1). |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Make no request and start no run: print the requests a step or a job makes, with placeholders. |
| `--plan` | `boolean` | - | Read GitHub and git, and write nothing: print the items the job takes and those it leaves out. This is the mode when no flag is given. |
| `--confirm` | `boolean` | - | Plan as --plan does, then run the items. It runs steps only when roadmap.implement.in_runner is true. Outside a runner, with --item, it starts the runner Job for that item instead; without --item it refuses. |
| `--why` | `boolean` | - | Also list the open items that the filter does not name, each with the family it misses, under 'Matched no filter'. Without it, the plan does not list them. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--wait` / `--no-wait` | `boolean` | `True` | Outside a runner: follow the Job's log and exit with its exit code. --no-wait prints the Job's name. |

---

## `devops roadmap plan-check`

**Check a plan pull request: the stage gates without a model, the token size of each task group, the title, the body, the `Semantic PR title` check and a base spec that moved since the plan. Details: docs/roadmap/plan-check.md.**

```bash
devops roadmap plan-check [OPTIONS] <pull_request>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pull_request>` | `integer` | Yes | The number of the plan pull request to check. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--json` | `boolean` | - | Print the problems as a JSON array of objects with path, rule and message. |
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |

---

## `devops roadmap plan-recheck`

**Check each change folder on the default branch again. Each folder gets one result: ok, rewrite, new-plan, delivered or cleanup, and each refusal names its gate. With --branch, list the refusals of each gate for the branch and the default branch, and mark each refusal that the branch adds as a case to review. A folder gets rewrite only when the mechanical rewrite of the plan fixes it. The command reads GitHub and git and calls no model. It writes no file unless you give --confirm. Details: docs/roadmap/plan-recheck.md.**

```bash
devops roadmap plan-recheck [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--source` | `path` | - | The clone of the repository. Without it, the model clone. |
| `--branch` | `string` | - | A ref of the clone, such as HEAD or origin/\<branch\>. The command judges its change folders on its own tree and compares them with the default branch. |
| `--json` | `boolean` | - | Print the folders, the counts and the refusals of each gate as JSON, with the result of each folder. |
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |
| `--confirm` | `boolean` | - | Write the rewritten files of each rewrite folder of the default branch to the working tree of --source. It needs --source. It writes no file if one differs from the default branch, and it makes no commit. Review the diff, and open a pull request. |

---

## `devops roadmap explain`

**Say, for one issue, whether the refine job, the stage job and the implement job take it. For each job the answer is yes, or no with the reason of the first rule that fails: the issue is closed or is no item, the filter, the rules of the job (the Status, the owner, the stop on record, the plan and the branch, and the setting roadmap.stage.planned_limit), and the limit of a run. For refine the reason is the wait of the item, such as a question for a person. The reasons are the texts of the 'Left out' list of stage --plan and implement --plan. The command reads GitHub and git, calls no model and writes nothing. It uses the filter and the limit that the Service uses for each job. A group over the step budget shows only when an earlier run recorded it.**

```bash
devops roadmap explain [OPTIONS] <item>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<item>` | `integer` | Yes | The issue number to explain. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--source` | `path` | - | Path to a clone of the repository. Without it, the command uses the model clone. |
| `--filter` | `string` | - | A label filter in the form family=value, for both jobs, over the families status, priority, type, value and effort. Repeat the option. Without it, each job uses its own default filter. |
| `--limit` | `integer` | - | Items a run takes, for both jobs. Without it, each job uses its own limit: the setting roadmap.stage.limit for stage, and 1 for implement. |
| `--trace` | `boolean` | - | Print the trace of the last run of the implement job for the issue, oldest event first, and no verdict. The command reads the one issue, and no clone, and writes nothing. |
| `--json` | `boolean` | - | Print the number and the totals of the last implement run of the issue as a JSON object: the tokens, the seconds, the repair rounds, the outcome counts and the count of dropped events. Each total is null when the record holds no trace of a run. The option cannot be used with --trace. |
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |

---

## `devops roadmap inbox`

**List what waits for a person in each repository of service.repos, or in the one that --repo names. Each line has its number, its age and the step that clears it, and an old wait is marked. It reads GitHub, calls no model and writes nothing; details: docs/roadmap/inbox.md.**

```bash
devops roadmap inbox [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--kind` | `choice (plan|implement|release|blocked|refine|split|alternatives|failed|draft|claim|labels|queue|person)` | - | List only the lines of one class, such as refine, split, alternatives, failed or draft. The counts of every class stay complete. |
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |

---

## `devops roadmap repair`

**Find the items that a placeholder reply of a model stalled. A returned item goes back to Ready. A stub refine item loses its stub section and its refine block. An item that a person set or answered stays as it is. This command reads GitHub and calls no model. It writes only with --confirm. Details: docs/roadmap/repair.md.**

```bash
devops roadmap repair [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--dry-run` | `boolean` | - | Make no request: print the requests that a run makes, in order, with placeholders. |
| `--confirm` | `boolean` | - | Make the writes to GitHub: set the Status of a returned item to Ready, and strip the section and clear the refine block of a stub item. |

---

## `devops roadmap return`

**Return an item to New with an evidence comment, handing it back to refinement when it cannot be built as specified or needs a refactor beyond its scope. The item gets the label status/new in place of its other status/* label.**

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
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--confirm` | `boolean` | - | Make the writes to GitHub: post the comment and set the Status to New (status/new). |

---

## `devops roadmap claim`

**Claim an item for an agent or a person with the label owner/agent or owner/human. An item has one owner. A person can take an item from the Service. The jobs stage and implement take no item that an agent or a person claimed.**

```bash
devops roadmap claim [OPTIONS] <item>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<item>` | `integer` | Yes | The issue or item number to claim. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--as` | `choice (agent|human)` | - | Who claims the item: agent or human. |
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--confirm` | `boolean` | - | Make the write to GitHub: set the owner label. |

---

## `devops roadmap release`

**Release an item: remove its owner/* label, whoever holds it. No job removes the claim of an agent or a person.**

```bash
devops roadmap release [OPTIONS] <item>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<item>` | `integer` | Yes | The issue or item number to release. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--confirm` | `boolean` | - | Make the write to GitHub: remove the owner label. |

---

## `devops roadmap eval`

**Score the plan and implement jobs on a golden set. Each command runs a job's real code on committed cases with a chosen model. It is on demand and no part of devops ci.**

```bash
devops roadmap eval COMMAND [ARGS]...
```

### `devops roadmap eval stage`

**Score the stage job on its golden set, the plans of 2026-11-01 with their known defects. For each case the job plans from the issue text, with the checks it runs in a Job. The command prints, for each type of defect that a gate catches, how often the first reply of the model avoids it, and a total score. It stores the report as JSON under the data directory. The model plans with the read-only toolbox of the job, which reads the code of the staging commit; with --no-toolbox it plans with one call and no tool. It calls the model through the gateway, one call per case at least. With --replay it calls no model: it runs the recorded plans through the gates and exits 1 when a gate stops refusing a known-bad plan or refuses a good plan. A live run leaves out a case that holds no commit and names it in the report. A change to the stage prompt or to the checks states this score before and after.**

```bash
devops roadmap eval stage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--case` | `string` | - | Run only this case, by folder name or issue number. Repeat the option for more cases. |
| `--model` | `string` | - | Model for the stage task. Without it, the configured model of the task. |
| `--limit` | `integer` | - | Run at most this many cases, the first ones of the set. |
| `--json` | `boolean` | - | Print the report as JSON in place of the table. |
| `--dry-run` | `boolean` | - | Make no request: list the cases and the model calls that a run makes. |
| `--replay` | `boolean` | - | Make no model call. Run the recorded plans through the gates and report which known defects each gate catches. |
| `--cases` | `path` | - | Folder of the cases. Default: tests/fixtures/roadmap_eval/stage. |
| `--source` | `path` | - | Repository that holds the staging commits of the cases. Default: this checkout. |
| `--no-toolbox` | `boolean` | - | Plan each case with one model call and no tool, as the job did before the toolbox. Run the same model with and without this option to compare the two scores. |

### `devops roadmap eval implement`

**Run one step of each fixture of the implement job in a scratch clone of this repository at the base commit of the fixture, with the chosen model, through the same step that the Job runs. Then evaluate six properties of the result: the tests it names pass, no test is deleted or renamed, the diff touches only the paths of the Changes line of the group, the verification commands of the group pass, no scratch file is in the diff, and the tasks of the group are ticked. The report lists the properties, the tokens, the model requests, the tool calls and the wall time of each fixture, and the property that failed first. A run writes a JSON report under eval/implement of the data directory. The command reads no GitHub state, writes none and pushes nothing. A change to the implement prompt or tool set states the score before and after.**

```bash
devops roadmap eval implement [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fixture`, `-F` | `string` | - | Run only the fixture with this name. Repeat the option. Without it, run every fixture. |
| `--fixtures` | `path` | - | Folder of the fixtures. Without it, the command uses tests/fixtures/roadmap_eval/implement of this checkout. |
| `--source` | `path` | - | Path to the clone of the repository to clone from. It must hold the base commit of each fixture. Without it, the command uses this checkout. |
| `--model`, `-m` | `string` | - | Model for the step, in place of the model of the task ai.tasks.implement. |
| `--json` | `boolean` | - | Print the report as JSON. |
| `--dry-run` | `boolean` | - | Make no request: list the fixtures and the model requests of the steps. Nothing is cloned and no model runs. |
| `--check-only` | `boolean` | - | Make no model call: evaluate the four properties that a diff decides on each recorded result of each fixture, and exit 1 when a result fails other properties than its record says. This is the offline mode. |
| `--run-commands` | `boolean` | - | With --check-only: clone the base, apply each recorded diff and run the two properties that run commands. |

### `devops roadmap eval intake`

**Run the intake duplicate evaluation set against the configured analysis model and print the score of each case. For each case intake plans the candidate in a roadmap that holds the case's item and nothing else, and writes nothing. The run makes one analysis call for each case, one at a time, and no embedding or GitHub request; it reads the type labels from .github/labels.yml of this checkout. It prints whether intake agrees with the person's verdict for each case, and the precision and the recall of the duplicate verdict. It exits 0 when every case ran, and 1 when a case could not run.**

```bash
devops roadmap eval intake [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Make no request: list the cases and the analysis call that a run makes for each. |

### `devops roadmap eval verify`

**Score the model verification pass of the stage job on the golden set. For each case the pass gets the issue, the recorded plan and the start of each file that the plan cites, reads the staging commit with the read tools of the planner, and returns findings of the nine defect types. The command prints the recall of the labeled defects (all, and the blocker and major ones), whether the recall of the blocker and major defects reaches the floor, the recall for each type, and the findings on the good plans. It matches each finding to one labeled defect of the same type. It stores the report as JSON under the data directory. It calls the model of the verification task through the gateway, one agent run per case, with one request for each model reply. It leaves out a case that holds no commit and names it in the report. A change of the model or of the prompt states this score.**

```bash
devops roadmap eval verify [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--case` | `string` | - | Run only this case, by folder name or issue number. Repeat the option for more cases. |
| `--model` | `string` | - | Model for the verification task. Without it, the configured model. |
| `--limit` | `integer` | - | Run at most this many cases, the first ones of the set. |
| `--json` | `boolean` | - | Print the report as JSON in place of the table. |
| `--dry-run` | `boolean` | - | Make no request: list the cases and the model calls that a run makes. |
| `--cases` | `path` | - | Folder of the cases. Default: tests/fixtures/roadmap_eval/stage. |
| `--source` | `path` | - | Repository that holds the staging commits of the cases. Default: this checkout. |

---
