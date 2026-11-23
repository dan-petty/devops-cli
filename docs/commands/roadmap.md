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
| `--full` | `boolean` | - | Read the whole issue listing and replace the snapshot of it under the data directory. Without it, a run reads only the issues changed since the snapshot. |
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
| `--item` | `integer` | - | Specific issue number to refine instead of selecting by priority. Refine refines it when it is open and New or Ready, even when nothing changed since its last round, whoever opened it, and however many comments refine wrote on it. It does not refine an item whose title type the branch types do not list. |
| `--limit` | `integer` | `7` | Maximum number of items to refine in this run (default 7). |
| `--dry-run` | `boolean` | - | Make no request and change no git ref: print what refine would plan and run, with placeholders. |
| `--confirm` | `boolean` | - | Refine the items and write the proposed designs to GitHub. Without it, refine prints its plan only. |

---

## `devops roadmap alternatives`

**Check open items for an open, maintained tool or library that already covers their need. A check writes a body block and posts a comment for a first check or a changed result, and a person decides what the tool means for the item. Details: docs/roadmap/alternatives.md.**

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
| `--source` | `path` | - | Path to a clone of the repository. The check reads the files of its deployed paths (roadmap.alternatives.inventory_paths) for the tools that the repository uses. Without it, the check reads the SBOM only. |

---

## `devops roadmap retitle`

**Shorten the title summary of open items that is over 60 characters, and correct a title type that the branch types do not list. The job keeps the type and the scope of a listed type. It writes fix(security) in place of the type security, with no model call, and comments once on another unlisted type. A Planned item takes the summary of its plan pull request title and needs no model call; another item gets one model call. The job leaves a title that a person changed after the last job comment. An item that the job leaves gets the mark retitle.skipped and one log line with the reason, and the job does not select it again until its title, body or plan pull request changes. Without --confirm, it prints the new titles and writes nothing.**

```bash
devops roadmap retitle [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--item` | `integer` | - | Specific issue number to examine instead of selecting. Retitle examines it when it is open and its title summary is over the limit or its title type is not listed. |
| `--limit` | `integer` | - | Maximum number of items to examine in this run (default: 25). The lowest numbers go first. |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, with placeholders. |
| `--confirm` | `boolean` | - | Write each new title to GitHub, and a comment on the item. |

---

## `devops roadmap consolidate`

**Propose groups of open items that share a root cause, and write the plan to a local file. A model proposes and then tries to refute each shortlist, code checks the answers, and nothing changes on GitHub. Details: docs/roadmap/consolidate.md.**

```bash
devops roadmap consolidate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to check the cited paths and lines against (default: the default branch of origin). The plan records its commit. |
| `--limit` | `integer` | - | Maximum number of shortlists to judge with the model in this run (default: 10). A shortlist that an earlier plan judged costs no call and does not count. |
| `--apply` | `string` | - | The id of a group of the last plan to apply. Needs --confirm to write. |
| `--decline` | `string` | - | The id of a group of the last plan to decline. The job record of its anchor keeps the id, and the group is not proposed again until its members change. Needs --confirm to write. |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, with placeholders. |
| `--confirm` | `boolean` | - | Confirm an apply of --apply or a decline of --decline. |

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
| `--job-item` | `integer` | - | Run as the stage Job of the one issue this number names: keep every rule of a round, plan and write that issue alone, and end with the exit code of the Job (0 result, 1 non-retryable failure, 75 evicted or retryable failure, 143 deadline). Needs --confirm and no --item. The pod of a Job from CronJob roadmap-stage runs it. Details: docs/roadmap/stage.md. |
| `--filter` | `string` | - | A label filter in the form family=value, over the families status, priority, type, value and effort. Repeat the option: the values of one family are alternatives, and the families all apply. The default is the setting roadmap.stage.filter. |
| `--limit` | `integer` | - | Maximum number of items to stage in this run. The default is the setting roadmap.stage.limit. |
| `--step-tokens` | `integer` | - | Most tokens that the inputs of one implementation step may hold. The default is the setting roadmap.stage.step_tokens. |
| `--dry-run` | `boolean` | - | Make no request: print the requests and the git commands that a run makes, with placeholders. |
| `--plan` | `boolean` | - | Read GitHub and call the model, make no GitHub write and no git write, and keep each plan that passes the checks as one local file: print the changes that --confirm writes. --confirm reads that file and asks the model nothing for an item whose input did not change. This is the mode when no flag is given. |
| `--confirm` | `boolean` | - | Plan as --plan does, then make the writes in git and on GitHub. A kept plan file of an item goes when the item is staged. |
| `--why` | `boolean` | - | Also list the open items that the filter does not name, each with the family it misses, under 'Matched no filter'. Without it, the plan does not list them. |
| `--phase` | `choice (prepare|agent|publish|all)` | `all` | The phase of the stage Job, with --job-item, --confirm and --work: prepare (the reads, the writes that need no model, and the clone of the stage agent with the dated scaffold), agent (the stock Coder agent, with no store and no GitHub credential), publish (the checks, the plan commit, the draft and the record), or all (the stage Job in one process, with no run folder). |
| `--work` | `path` | - | The run folder of a phase other than all: state/, work/ and out/. |

---

## `devops roadmap run`

**Run the roadmap jobs that are due, in order: metrics, then intake, refine and the alternatives check, and record each one's last success. Intake is due on an issue reopened or a new issue, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every roadmap.refine.interval_minutes (7 by default), on a first run, and after an intake that placed a critical fix or a P0 item; retitle is due every 61 minutes and on a first run; the alternatives check is due every roadmap.alternatives.interval_minutes (239 by default) and on a first run, and checks at most roadmap.alternatives.first_pass_limit items while an item has no check, and roadmap.alternatives.limit items after. A row whose last round counted roadmap.\<row\>.backlog_threshold or more items in its queue is due every roadmap.\<row\>.backlog_interval_minutes. Without --confirm, or with --dry-run, prints the due list and runs nothing.**

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

**Implement a Staged or Planned item in bounded steps: with --group, run one task group in a checkout; without it, run the job, which takes items, runs their steps, and opens or updates the draft pull request. Details: docs/roadmap/implement.md.**

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
| `--rebase` / `--no-rebase` | `boolean` | `True` | Rebase the branch onto the tip of the default branch that prepare recorded, before the first step. --no-rebase skips the rebase, and publish puts the work on the old tip. |
| `--why` | `boolean` | - | Also list the open items that the filter does not name, each with the family it misses, under 'Matched no filter'. Without it, the plan does not list them. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--wait` / `--no-wait` | `boolean` | `True` | Outside a runner: follow the Job's log and exit with its exit code. --no-wait prints the Job's name. |
| `--phase` | `choice (prepare|agent|publish|all)` | `all` | The phase of the run, with --confirm and --item: prepare (the claim, the clone and the Status, with no code of the pull request), agent (the steps, with no GitHub call), publish (the patches, the draft and the record), or all (the three in one process). |
| `--work` | `path` | - | Run folder of a phase other than all: state/, work/ and out/. |

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

**Check each change folder on the default branch again. Each folder gets one result: ok, rewrite, new-plan, delivered or cleanup, and each refusal names its gate. With --branch, list the refusals of each gate for the branch and the default branch, and mark each refusal that the branch adds as a case to review. A folder gets rewrite only when the mechanical rewrite of the plan fixes it. With --branches, judge the change folder of each open draft plan pull request whose base is the default branch, and with --confirm, rebase it, rewrite it, check it and push it once with a lease. The command reads GitHub and git and calls no model. It writes no file unless you give --confirm. Details: docs/roadmap/plan-recheck.md.**

```bash
devops roadmap plan-recheck [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--source` | `path` | - | The clone of the repository. Without it, the model clone. |
| `--branch` | `string` | - | A ref of the clone, such as HEAD or origin/\<branch\>. The command judges its change folders on its own tree and compares them with the default branch. |
| `--branches` | `boolean` | - | Judge the change folder of each open draft plan pull request whose base is the default branch. Without --confirm, it prints the result of each branch and pushes nothing. With --confirm, it rebases the branch onto the default branch, writes the mechanical rewrite, checks it and pushes it once with a lease. A branch whose plan the rewrite does not change gets no rebase and no push, and a conflict or a refused rewrite leaves the branch as it is. It takes no --branch and no --json. |
| `--base` | `string` | - | A commit, with --branch: make no fetch, read no ref of the default branch, and judge only the change folders that the branch changes from this commit, with the rules of the stage plan. The command exits 1 when one of these folders is not ok. The stage agent runs it on its clone. |
| `--candidate` | `path` | - | The body candidate of the stage agent, with --base: the line '# <summary>', then the text of the body. The title and the body rules judge the texts that the stage Job builds from it. |
| `--issues` | `path` | - | An issue listing, a JSON list of issues with the number, the title, the URL and the state: the command reads the issues from it and opens no store. |
| `--json` | `boolean` | - | Print the folders, the counts and the refusals of each gate as JSON, with the result of each folder. |
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |
| `--confirm` | `boolean` | - | Write the rewritten files of each rewrite folder of the default branch to the working tree of --source, and make no commit. It needs --source, and it writes no file if one differs from the default branch. With --branches, rebase, rewrite, check and push each open plan branch whose rewrite changes a file, once, with a lease on the head that the run read. Review the diff, and open a pull request. |

---

## `devops roadmap explain`

**Say, for one issue, whether the refine job, the stage job and the implement job take it. For each job the answer is yes, or no with the reason of the first rule that fails: the issue is closed or is no item, the filter, the rules of the job (the Status, the owner, the stop on record, the plan and the branch), the setting roadmap.stage.planned_limit, which is a rule of the stage job only, and the limit of a run. For refine the reason is the wait of the item, such as a question for a person. For a stopped item it prints the state of the stop from the job record: the class, the attempts of the stopped step and the action left. The reasons are the texts of the 'Left out' list of stage --plan and implement --plan. The command reads GitHub and git, calls no model and writes nothing. It uses the filter and the limit that the Service uses for each job. A group over the step budget shows only when an earlier run recorded it.**

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

## `devops roadmap follow`

**Show the run of one issue: the trace of the last run of the implement job as the table of the pull request comment, then the masked tail of the log of the pod of its runner Job while the Job runs. The command reads the issue once, which is one GitHub request, and reads the log through the Kubernetes API with the kubeconfig of the caller, which needs get and list on pods and get on pods/log. It calls no model and writes nothing; details: docs/ROADMAP_WORKFLOW.md.**

```bash
devops roadmap follow [OPTIONS] <item>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<item>` | `integer` | Yes | The issue number of the item whose run to show. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--lines` | `integer` | `100` | Number of last lines of the log of the pod of the runner Job to print. |
| `--dry-run` | `boolean` | - | Make no request: print the one read that a run makes, with a placeholder. |

---

## `devops roadmap inbox`

**List what waits for a person in each repository of service.repos, or in the one that --repo names. Each line has its number, its age and the step that clears it, the line of a stopped item names the class and the action left, and an old wait is marked. It reads GitHub, calls no model and writes nothing; details: docs/roadmap/inbox.md.**

```bash
devops roadmap inbox [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--kind` | `choice (plan|implement|release|blocked|refine|split|alternatives|failed|stage_retry|draft|claim|labels|queue|person|owner)` | - | List only the lines of one class, such as refine, split, alternatives, failed, draft or owner. The counts of every class stay complete. |
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |

---

## `devops roadmap registries`

**List each module-level REGISTRY_COUNTS entry of the test modules with its token, its kind, its target path and its source path:line. It warns on a length ratchet and on a limit tuple that no declaration of the module covers, and on a declaration that is no plain literal, and it exits 1 on a finding. It reads each module with ast, imports no test module and writes nothing.**

```bash
devops roadmap registries [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path` | `path` | - | The checkout whose tests folder the audit reads (default: the repository root of the current folder). |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

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

**Score the roadmap jobs. grades reads the live result lines of each job in Loki. Each other command runs a job's real code on committed cases with a chosen model. Each is on demand and no part of devops ci.**

```bash
devops roadmap eval COMMAND [ARGS]...
```

### `devops roadmap eval stage`

**Score the stage job on its golden set, the plans of 2026-11-01 with their known defects. For each case the job plans from the issue text, with the checks it runs in a Job. The command prints, for each type of defect that a gate catches, how often the first reply of the model avoids it, and a total score. It stores the report as JSON under the data directory. The model plans with the read-only toolbox of the job, which reads the code of the staging commit; with --no-toolbox it plans with one call and no tool. The toolbox is the one of --toolset, or the configured roadmap.stage.toolset, and the report names it. It calls the model through the gateway, one call per case at least. With --replay it calls no model: it runs the recorded plans through the gates and exits 1 when a gate stops refusing a known-bad plan or refuses a good plan. A live run leaves out a case that holds no commit and names it in the report. A change to the stage prompt or to the checks states this score before and after.**

```bash
devops roadmap eval stage [OPTIONS] <form>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<form>` | `string` | No | The form `compare <toolset>...`: run two or more toolsets over the same cases and print one table with the defects, the tool calls, the requests, the tokens, the time and the cost of each toolset, and one delta line against the first. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--case` | `string` | - | Run only this case, by folder name or issue number. Repeat the option for more cases. |
| `--model` | `string` | - | Model for the stage task. Without it, the configured model of the task. |
| `--toolset` | `choice (base|extended|research)` | - | The tools of each plan run: base, extended or research. Without it, the setting roadmap.stage.toolset. The report names the toolset that the run read. |
| `--limit` | `integer` | - | Run at most this many cases, the first ones of the set. |
| `--runs` | `integer` | `3` | Run each case this many times in the compare form, and report the minimum and the maximum of each measured value. Default: 3. |
| `--verify` | `boolean` | - | In the compare form, run the verification pass on the plan of each run and report the defects that it finds. Without it, the verification column says `not run`. |
| `--json` | `boolean` | - | Print the report as JSON in place of the table. |
| `--dry-run` | `boolean` | - | Make no request: list the cases and the model calls that a run makes. |
| `--replay` | `boolean` | - | Make no model call. Run the recorded plans through the gates and report which known defects each gate catches. |
| `--record` | `boolean` | - | Write the constants that the plan of each case cites into its facts file. |
| `--cases` | `path` | - | Folder of the cases. Default: tests/fixtures/roadmap_eval/stage. |
| `--staged-cases` | `path` | - | In the compare form, the folder of the staged-item replay cases, in the same case format as the golden set. Default: tests/fixtures/roadmap_eval/staged. |
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
| `--no-tools` | `boolean` | - | Run the selected fixtures with the remote MCP tools of the step off. Run the same model with and without this option to compare the two scores. |
| `--json` | `boolean` | - | Print the report as JSON. |
| `--dry-run` | `boolean` | - | Make no request: list the fixtures and the model requests of the steps. Nothing is cloned and no model runs. |
| `--check-only` | `boolean` | - | Make no model call: evaluate the four properties that a diff decides on each recorded result of each fixture, and exit 1 when a result fails other properties than its record says. This is the offline mode. |
| `--run-commands` | `boolean` | - | With --check-only: clone the base, apply each recorded diff and run the two properties that run commands. |

### `devops roadmap eval intake`

**Run the intake duplicate evaluation set against the model of the task intake and print the score of each case. For each case intake plans the candidate in a roadmap that holds the case's item and nothing else, and writes nothing. The run makes one intake call for each case, one at a time, and no embedding or GitHub request; it reads the type labels from .github/labels.yml of this checkout. It prints whether intake agrees with the person's verdict for each case, and the precision and the recall of the duplicate verdict. It exits 0 when every case ran, and 1 when a case could not run.**

```bash
devops roadmap eval intake [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Make no request: list the cases and the intake call that a run makes for each. |

### `devops roadmap eval jev`

**Compare Jev (typesafe/jev-1.14) with the triage model on the proposal fields of intake. Both models run the duplicate cases of the intake evaluation set and the label cases, which are closed issues with the type, priority, Value and Effort that a person set. It prints the false duplicates of each model first, then how often each label field agrees with the person's. It ends with the verdict on the setting roadmap.intake.jev: set it to on only when Jev flags no more false duplicates than the triage model. The run sends two model calls for each case, one at a time, and no embedding or GitHub request. It stops before the first call when it needs more calls than --max-calls. A case that a model gives no answer for counts as not agreed, and the report counts it. With --from-shadow, it reads the shadow records of intake instead. It exits 0 after it prints the report.**

```bash
devops roadmap eval jev [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Make no request: print the number of calls that a run makes and the limit. |
| `--max-calls` | `integer` | `160` | The most model calls that a run may make. A run that needs more stops before its first call. The default keeps the spend of a run under 1 USD. |
| `--min-confidence` | `float` | `0.0` | The least confidence of a Jev choice or score answer that the run takes. A lower answer counts as no answer, as in intake, where the least is 0.60 and the triage model decides the proposal. The default 0 takes every answer, to measure what Jev knows. |
| `--from-shadow` | `boolean` | - | Read the shadow records of Jev instead of running the cases. While roadmap.intake.jev is shadow, intake records the Jev answers of each new candidate in the job record of its issue. This option reads every issue of the repository, joins each record with the labels the issue holds now, and prints for each field how often Jev and the triage model agree, how often each equals the final label, and how often Jev equals it in each band of its probability. It also counts the duplicate flags against the issues closed as a duplicate. It makes no model request and no write, and it ignores --max-calls and --min-confidence. |
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |

### `devops roadmap eval verify`

**Score the model verification pass of the stage job on the golden set. For each case the pass gets the issue, the recorded plan and the start of each file that the plan cites, reads the staging commit with the read tools of the planner, and returns findings of the nine defect types. The command prints the recall of the labeled defects (all, and the blocker and major ones), whether the recall of the blocker and major defects reaches the floor, the recall for each type, the findings on the good plans, and whether the mean of the blocker and major findings for each good plan passes the ceiling. It matches each finding to one labeled defect of the same type. It stores the report as JSON under the data directory and writes it again when each case ends, so a stopped run keeps the cases that ended. It calls the model of the task stage_review through the gateway, one agent run per case, with one request for each model reply. It leaves out a case that holds no commit and names it in the report. A change of the model or of the prompt states this score.**

```bash
devops roadmap eval verify [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--case` | `string` | - | Run only this case, by folder name or issue number. Repeat the option for more cases. |
| `--model` | `string` | - | Model for the task stage_review. Without it, the configured model of that task. |
| `--limit` | `integer` | - | Run at most this many cases, the first ones of the set. |
| `--json` | `boolean` | - | Print the report as JSON in place of the table. |
| `--dry-run` | `boolean` | - | Make no request: list the cases and the model calls that a run makes. |
| `--cases` | `path` | - | Folder of the cases. Default: tests/fixtures/roadmap_eval/stage. |
| `--source` | `path` | - | Repository that holds the staging commits of the cases. Default: this checkout. |
| `--resume` | `path` | - | A report of this command. Run only the cases that the report lacks or that failed in it, and update the report in place. The model of the run must be the model of the report. |

### `devops roadmap eval screen`

**Score the Jev screen before the verify step against the reviewer alone. For each case of the golden set the command asks Jev the questions of the screen about the digest of the plan, and reads what stored runs of the reviewer (devops roadmap eval verify) found there. It fits the cuts on one fixed half of the cases, scores them on the other half, and repeats with the halves swapped. It prints the skipped reviews, the serious defects that the cascade loses, the false clears, the cost, and whether the bar of the pilot is met. It calls no reviewer. It stores the report as JSON under the data directory.**

```bash
devops roadmap eval screen [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviewer` | `path` | - | A report of devops roadmap eval verify with the reviewer alone. Repeat the option to merge reports; a later report wins for a case. |
| `--from` | `path` | - | A report of this command. Fit again from its rows and make no request. |
| `--reviewer-usd` | `float` | - | The price in USD of one review of the reviewer alone, for the cost line. |
| `--write-cuts` | `boolean` | - | Fit the cuts on all the reviewed cases and write the data file of the screen. |
| `--json` | `boolean` | - | Print the report as JSON in place of the table. |
| `--dry-run` | `boolean` | - | Make no request: list the cases and the model calls that a run makes. |
| `--cases` | `path` | - | Folder of the cases. Default: tests/fixtures/roadmap_eval/stage. |

### `devops roadmap eval completeness`

**Score the Jev completeness check of the draft pull requests on a labelled set. The set holds the diffs of merged pull requests whose issue lists acceptance criteria (complete drafts), and incomplete drafts: plans that the stage golden set labels with a dropped criterion, and merged diffs from which one hunk is removed. For each case the command makes one request to Jev (a Noul question for each criterion and a Score question for the tests) and prints the recall of the incomplete drafts, the false holds on the complete drafts, the same rates at other thresholds, the spend, and whether the switch roadmap.stage.jev_completeness stays off. It stores the report as JSON under the data directory, with the probability of each criterion.**

```bash
devops roadmap eval completeness [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--limit` | `integer` | - | Run at most this many cases, the first ones of the set. |
| `--json` | `boolean` | - | Print the report as JSON in place of the table. |
| `--dry-run` | `boolean` | - | Make no request: list the cases and the model calls that a run makes. |
| `--cases` | `path` | - | Folder of the cases. Default: tests/fixtures/roadmap_eval/completeness. |

### `devops roadmap eval grades`

**Print the job grade of each roadmap workflow and repository from its result lines in Loki (docs/roadmap/job-success.md). For each row: the attempts with no infrastructure cut, the successes, p, the Wilson 95% interval, the grade (100, 90, 80, 70, 60, <60, or too few under 30 attempts), the point grade and the range of grades of the interval, the first-pass ratio, the all-attempts ratio and the infrastructure share, the top 3 failure classes, the owner action of the grade, the tokens and seconds of each attempt and of each success, each version with 10 attempts or more, the attempts in 24 h and in 6 h, and the broken and infrastructure signals. It sends LogQL metric queries to the instant query endpoint of Loki and changes nothing. The 100 grade needs the first-pass counts that only the stage, implement and fix_plan lines hold today. For stage and implement it also reads the pull requests of the bot of service.github_app.slug that changed in the window (updated:>=), with one GraphQL search to GitHub for each 100, and gives the share of each first verdict label and the verdict score beside p, for the pull requests opened in the window. It scores the drafted lines of implement of each pull request once, by its forge state: merged or out of draft gives 1 success and a failure for each other line, closed gives a failure for each line, and a draft keeps its lines out of the attempts in drafts_pending.**

```bash
devops roadmap eval grades [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo` | `string` | - | Report only this repository (owner/name). Default: all repositories. |
| `--window` | `choice (6h|24h|7d)` | `7d` | The window of the grade. The policy grade uses 7d; the trend columns always show 24h and 6h. |
| `--loki-url` | `string` | - | The Loki to query. Without it, the loki.url setting, else http://localhost:3100. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Send no request: print the LogQL queries that a run sends. |

### `devops roadmap eval harbor`

**Export an implement eval fixture as a Harbor task, and run the trials of one task with the Harbor command line. Harbor (harbor-framework/harbor) runs one agent on one task in a container N times and reports the reward of each trial, so the numbers compare with those of another harness. Both commands are on demand and no part of `devops ci`, and the harbor program and the Docker engine go through the process seam.**

```bash
devops roadmap eval harbor COMMAND [ARGS]...
```

#### `devops roadmap eval harbor export`

**Write one Harbor task folder for each chosen fixture: instruction.md, the environment Dockerfile, tests/test.sh and task.toml. The instruction holds the issue and the plan of the fixture, and the test script writes the reward of a trial. A fixture that lacks its issue text, a plan file or a test command is refused.**

```bash
devops roadmap eval harbor export [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fixture`, `-F` | `string` | - | Export only the fixture with this name. Repeat the option. Without it, export every fixture. |
| `--fixtures` | `path` | - | Folder of the fixtures. Without it, the command uses tests/fixtures/roadmap_eval/implement of this checkout. |
| `--out` | `path` | - | Folder of the task folders. Without it, the command writes them under eval/harbor/tasks of the data directory. |
| `--timeout` | `integer` | `600` | Time limit of one trial in seconds, written into the task configuration. The default is 600. |
| `--json` | `boolean` | - | Print the report as JSON. |
| `--dry-run` | `boolean` | - | Write no file: list the task folders that an export would write. |

#### `devops roadmap eval harbor run`

**Run N trials of one Harbor task folder with the harbor program, read the reward and the cost of each trial, and write the pass rate, the trial count and the total cost as result.json under eval/harbor of the data directory. A trial with no reward or no cost is refused.**

```bash
devops roadmap eval harbor run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--task` | `path` | - | Folder of the Harbor task to run. |
| `--trials` | `integer` | `1` | Number of trials of the task. The default is 1. |
| `--agent` | `string` | - | Agent that Harbor runs, by its import path (`module.path:ClassName`). The default is the Coder harness of the Service. |
| `--model` | `string` | - | Model of the agent. The default is devops-coder. |
| `--provider` | `string` | - | Sandbox provider of the trial. The default is docker, the Docker engine of the workstation. |
| `--json` | `boolean` | - | Print the report as JSON. |
| `--dry-run` | `boolean` | - | Start no program: print the harbor command that a run would start, with a placeholder for the folder of its job. |

---

## `devops roadmap review`

**Review a version range or a period of a repository: the facts of the window, each with its source, its query and the time of its read.**

```bash
devops roadmap review COMMAND [ARGS]...
```

### `devops roadmap review run`

**Read the git facts of one window from the checkout of the working directory and write data.json and its JSON Schema. The window is half-open: the base commit and the start time are out, and the head commit and the end time are in. A tag becomes its commit. A time becomes the last first-parent commit of the default branch at or before it. Each time is in UTC before any compare. The facts are the commits and their types, the net change and the churn with the generated files apart, the release tags, the hot files with their renames followed, and the complexity of the hottest files (lizard, the extra review). Then the command reads each fact of the catalog (catalog.yaml) at the end of the window: the issue listing, GitHub releases, Actions runs and code-scanning alerts, Prometheus (prometheus.url), Loki (loki.url) and OpenSpec. A source past its retention gives expired, an unset setting gives skipped and a failed read gives error, never 0. data.json also lists the facts that must agree and do not.**

```bash
devops roadmap review run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version` | `string` | - | Two version tags as A..B. The commits after A up to B, and the tags created after A up to B. |
| `--since` | `string` | - | The start time, in ISO 8601, with --until. A time with no offset is in UTC. |
| `--until` | `string` | - | The end time, in ISO 8601, with --since. A time with no offset is in UTC. |
| `--week` | `string` | - | One ISO week as YYYY-Www, from Monday 00:00 UTC to the next Monday. |
| `--last` | `string` | - | The days up to now as Nd, such as 7d, from the start of this minute. |
| `--repo`, `-R` | `string` | - | The repository as owner/name (default: the origin of the checkout). It must be the origin of the checkout. |
| `--out` | `path` | - | The folder of data.json (default: project-review/\<owner\>/\<name\>/<window id> under the data directory). |
| `--json` | `boolean` | - | Print data.json to standard output. |
| `--dry-run` | `boolean` | - | Start no program and send no request: print the git commands that a run starts, then the shared reads, then each fact of the catalog with its reader kind and its query, with placeholders. |

---

## `devops roadmap step`

**Run one step of a roadmap job by hand, the same way the Service runs it. Each step has one purpose. Details: docs/roadmap/stage.md.**

```bash
devops roadmap step COMMAND [ARGS]...
```

### `devops roadmap step fix-checks`

**Repair a failed check of an open pull request (#5023).**

```bash
devops roadmap step fix-checks [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--pull`, `-p` | `integer` | - | Number of the pull request to repair. |
| `--head` | `string` | - | Expected commit SHA of the pull request head. |
| `--check` | `string` | - | Name of the failed check to repair (default: the first failed check). A check that does not fail on the head gives skipped. |
| `--confirm` | `boolean` | - | Repair and push in a runner Job. Without it, the step prints its plan and writes nothing. |
| `--phase` | `choice (prepare|agent|publish|all)` | `all` | The phase of the repair, with --confirm: prepare (the GitHub reads, the claim and the clone, with no agent code), agent (the fixers, with no GitHub call), publish (the patch as one commit, the push with a lease and the GitHub writes), or all, the three in one process. Without --confirm, prepare runs the plan, and agent and publish do nothing. |
| `--work` | `path` | - | The run folder of a phase other than all: state/ for prepare and publish, work/ for the clone and the inputs of the agent, and out/ for its outputs. |
| `--dry-run` | `boolean` | - | Make no network request and change nothing. |

### `devops roadmap step fix-conflict`

**Settle merge conflicts on a bot pull request with the default branch (#5019). Tier 1 settles archive, generated document and lockfile conflicts with no model: it runs devops docs generate or uv lock, which run code of the pull request. So tier 1 and the push run only with --confirm in a runner Job. Without --confirm, the step prints its plan, runs no code of the pull request and writes nothing.**

```bash
devops roadmap step fix-conflict [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--pull`, `-p` | `integer` | - | The pull request number to settle merge conflicts for. |
| `--head` | `string` | - | Expected head SHA of the pull request. Refuses to run if remote head moved. |
| `--confirm` | `boolean` | - | Settle and push in a runner Job. Without it, the step prints its plan and writes nothing. |
| `--phase` | `choice (prepare|agent|publish|all)` | `all` | The phase of the round, with --confirm: prepare (the GitHub reads, the bounds, the clone and the conflicts, with no code of the pull request), agent (the rebase and tier 1, with no GitHub call), publish (the push with a lease and the record), or all, the three in one process. Without --confirm, prepare and all print the plan, and agent and publish do nothing. |
| `--work` | `path` | - | The run folder of a phase other than all: state/ for prepare and publish, work/ for the clone and the inputs of the agent, and out/ for its outputs. |
| `--dry-run` | `boolean` | - | Make no external requests: display planned actions. |

### `devops roadmap step fix-plan`

**Repair one open plan pull request that holds the label verdict/fix-plan: the stage planner revises the plan with the open findings of a model review, and a better revision is pushed. Without --confirm, print the plan pull request that it selects. Details: docs/roadmap/stage.md.**

```bash
devops roadmap step fix-plan [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--source` | `path` | - | Path to a clone of the repository at its default branch. Without it, the job clones the repository into its own model clone, updates it, and uses it. |
| `--item` | `integer` | - | Judge the one item that this number names, instead of each Staged item by priority. |
| `--pull` | `integer` | - | Judge the one item whose record holds this plan pull request number in stage.pr. |
| `--dry-run` | `boolean` | - | Make no request: print the requests, the git commands and the writes of a run, with placeholders. |
| `--confirm` | `boolean` | - | Run the attempt: call the models, push a better revision, and write the label, the comment and the record. It acts in every mode of roadmap.fix_plan.mode. |
| `--skip-wait` | `boolean` | - | Leave out the wait of 6 hours after the last attempt, for the one item that --item or --pull names. Needs --confirm. The limits of roadmap.fix_plan.head_attempts on the head and roadmap.fix_plan.revisions stay, but a head whose counted attempts ran on an older release gets one more attempt. The Service never uses it. |

### `devops roadmap step open`

**Open, update, or recover the draft pull request of an item (#5020).**

```bash
devops roadmap step open [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--item`, `-i` | `integer` | - | Number of the item to open or update a pull request for. |
| `--head` | `string` | - | Branch to open the pull request from. |
| `--base` | `string` | - | Base branch the pull request merges into. |
| `--title` | `string` | - | Title of the pull request. |
| `--body` | `string` | - | Body of the pull request. |
| `--kind`, `-k` | `string` | `plan` | Kind of the pull request (plan or delivery). |
| `--dry-run` | `boolean` | - | Make no request to GitHub or git, and write no record key. |

### `devops roadmap step ready`

**Mark a draft pull request ready for review after checks pass (#5021).**

```bash
devops roadmap step ready [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--pull`, `-p` | `integer` | - | Number of the pull request to mark ready. |
| `--head` | `string` | - | Expected commit SHA of the pull request head. |
| `--force`, `-f` | `boolean` | - | Bypass draft readiness verification. |
| `--dry-run` | `boolean` | - | Make no network request and mark nothing ready. |

### `devops roadmap step review`

**Give a bot pull request one verdict: mergeable, needs fix, discard or issue changed (#5969).**

```bash
devops roadmap step review [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--pull`, `-p` | `integer` | - | Number of the pull request to review. |
| `--head` | `string` | - | Expected commit SHA of the pull request head. |
| `--source` | `path` | - | Clone of the repository that a discard deletes the branch from (default: the clone model-clone of the data folder). |
| `--confirm` | `boolean` | - | Write the verdict and take its next action in a runner Job, in the mode on of roadmap.review.mode. Without it, the step prints the verdict and writes nothing. |
| `--dry-run` | `boolean` | - | Make no network request and change nothing. |

### `devops roadmap step watch`

**Watch pull request checks and state until the verdict settles (#5021).**

```bash
devops roadmap step watch [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--pull`, `-p` | `integer` | - | Number of the pull request to watch. |
| `--head` | `string` | - | Expected commit SHA of the pull request head. |
| `--block` / `--no-block` | `boolean` | `True` | Wait until the checks settle or timeout passes. |
| `--timeout` | `integer` | `3600` | Maximum seconds to wait in block mode. |
| `--interval` | `integer` | `60` | Seconds between poll requests in block mode. |
| `--dry-run` | `boolean` | - | Make no network request and output no verdict. |

---
