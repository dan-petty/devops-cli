# `devops roadmap`

Read and write the roadmap on GitHub, its source of truth: issues, their labels and milestones.

## Commands

## `devops roadmap intake`

**Turn candidates into items: every open issue with no priority/* label. The model compares each with the items and the issues closed as not planned, but not with an issue that has sub-issues, because its sub-issues deliver it. It names a possible duplicate for a person to close: intake never closes an issue and never drops a candidate. Each gets a type label and a scope label from the Conventional Commit title, a status/new label, Value and Effort labels and a reason comment, then its priority label last, and goes to the backlog. The model picks the type only for a title with no Conventional Commit type. A label a person set stays. Intake sets no milestone: a person plans the milestones, and a milestone an issue has stays. Close an issue as not planned to keep it off the roadmap: devops gh issues close \<number\> --reason not-planned. A candidate an agent files with --title and --body-file is labeled source/agent, and intake files it, a possible duplicate too, unless a run that stopped after filing left an open issue with its title and body, which intake then places; a text that looks like it holds a secret is refused. --dry-run makes no request and prints the requests a run makes; --plan, the default, reads GitHub and calls the model, writes nothing and reports what it spent; --confirm makes the writes.**

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

## `devops roadmap intake-eval`

**Run the intake duplicate evaluation set against the configured analysis model and print the score of each case. For each case intake plans the candidate in a roadmap that holds the case's item and nothing else, and writes nothing. The run makes one analysis call for each case, one at a time, and no embedding or GitHub request; it reads the type labels from .github/labels.yml of this checkout. It prints whether intake agrees with the person's verdict for each case, and the precision and the recall of the duplicate verdict. It exits 0 when every case ran, and 1 when a case could not run.**

```bash
devops roadmap intake-eval [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Make no request: list the cases and the analysis call that a run makes for each. |

---

## `devops roadmap refine`

**Refine roadmap items to Ready with proposed design, tasks, and acceptance criteria, using code and documentation. When a fact or a decision has no verified source, or a key question of the body has no answer, refine investigates it with tools that read the code and, for a public repository with a Firecrawl key, search the web. A design question gets the best-practice option with the options it compared, and only a decision that a person must make waits on a person. The plan says when web search is off. Without --item, refine takes items nearest place first: each open milestone's New items, by due date and then by number, then the backlog's P0 and P1 items, then the backlog's other New items, each place by priority. Only --limit stops a run. The number of Ready items does not stop it. In each open milestone and among the backlog's P0 and P1 items it also takes Ready items it has no record of, and sets one back to New when it finds it not ready. An item that an account other than the owner, a member or a collaborator opened waits on a person, and only --item refines it. An item on which refine wrote 2 comments in the last 24 hours also waits on a person and takes no place under --limit, and only --item refines it until the older comment is 24 hours old. An item refine cannot set to Ready gets one comment with its next step. The step is the questions a person answers, the split a person makes, or the open items it waits on. Refine looks at the item again after a reply, a body edit or the close of those items, or after a commit on the default branch changes a file that the block cites. The report groups every item by its next step. An item whose model call fails is skipped and reported; the others are still refined, and refine then exits 1.**

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

**Check open items for an open, maintained tool or library that already covers their need, in whole or in part. For each item, one agent run searches the web with Firecrawl and reads the facts of each candidate from GitHub and PyPI: its license, its last activity and whether it is archived. The verdict is covers, partly, none or not-applicable. With --confirm, a check posts one comment, replaces the block `devops-roadmap-alternatives` in the item's body, and records the check in the job record. It changes no label and closes no issue. A person decides what a tool means for the item. The run takes open New and Ready items that a person with write access opened: first the items with no check, lowest number first, then the items whose check is older than roadmap.alternatives.recheck_days or whose text changed since. The check is off, and the plan says why, for a private repository or with no Firecrawl key. An item whose model call fails or whose reply cites a URL that no tool returned is skipped and reported; the others are written, and the command then exits 1.**

```bash
devops roadmap alternatives [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--item` | `integer` | - | Specific issue number to check instead of selecting. Alternatives checks it when it is open, whoever opened it and whatever its status, even when its check is current. |
| `--limit` | `integer` | - | Maximum number of items to check in this run (default: roadmap.alternatives.limit, 5). |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, with placeholders. |
| `--plan` | `boolean` | - | Run the checks and print them, and write nothing. This is the default. |
| `--confirm` | `boolean` | - | Write each check to GitHub: its comment, its body block and its job record. |

---

## `devops roadmap stage`

**Make Ready items Staged: for each item that a label filter names, make the branch \<type\>/\<issue\>-\<slug\> at the fetched default branch, write the OpenSpec change of the item in task groups that each fit the step budget, make one commit as the identity of the session, push it, and open a draft pull request whose title is `docs(openspec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The branch keeps the type of the issue. The Status of the item stays Ready, and the job does not mark the pull request ready: the Service does, in its row stage_ready, when all checks of the draft have passed. One comment on the issue names the branch, the pull request and the task groups with their measures. The default filter is status=ready: the job takes the Ready items of any type, priority and effort, the highest priority first. The job leaves out an item that is not Ready, an item with the label needs-split, an item that an account without write access opened, an item that depends on an open issue, an item that a pushed branch or a worktree holds, an item whose plan is on the default branch or whose change is archived there, and an item whose text looks like a secret; the plan says why. A task group over the budget goes back to the model once, and a group still over it stops the item. An item whose model call fails is skipped and reported, the others are still staged, and the command then exits 1. Each run also removes the draft and the branch of a closed item when only the identity of the session wrote to them.**

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

**Run the roadmap jobs that are due, in order: metrics, then intake, refine and the alternatives check, and record each one's last success. Intake is due on an issue reopened, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every 31 minutes, on a first run, and after an intake that placed a critical fix or a P0 item; the alternatives check is due every 719 minutes and on a first run, and checks at most roadmap.alternatives.limit items. Without --confirm, or with --dry-run, prints the due list and runs nothing.**

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

**Implement a Staged item, in bounded steps. With --group it runs one task group of the change of an item in the checkout --source: the agent is pydantic-ai's Coder on the model of ai.tasks.implement. Its inputs are the item's title, problem and acceptance criteria, the change's proposal, design and tasks, the group, and the files the group names. The command refuses to start when they do not fit the window of the task, or when the checkout has uncommitted changes. The shell of the agent runs only git, uv, ruff and mypy, with a scratch home. When the agent returns, the command runs the verification commands of the group, ruff on the changed Python files, and mypy on the changed files that the type check of devops ci covers (the files under src, with its options), and checks that the agent made no commit, removed or renamed no test that existed at the start of the step, and ticked every task of the group. Before these checks it deletes each new file that git does not ignore, that the group does not name, and that is outside src, tests, docs and openspec, and lists the files in the report. The command writes the tasks file back to its text before the run and keeps only the ticks of the group, so no edit of that file stops the step. It then runs the pre-commit stage of the hooks of the repository on the staged changes. An agent whose ruff, mypy or hook fails, or that forgets a tick, gets more turns, at most roadmap.implement.repair_rounds of them, that may change only the files it changed. When every check passes, it commits the checkout as '<group title> (#\<item\>)'. Otherwise it resets the checkout to the commit where the step started, reports the step as stopped with the reason and the masked diff of the work it discarded, and exits 1. It writes nothing to GitHub. Without --group it is the job. It takes each Staged or Planned item that a label filter names (default: status=ready, status=planned, effort=low). A Staged item has its staged branch and draft on origin. A Planned item has its change folder on the default branch and no branch: the job makes the branch \<type\>/\<issue\>-\<slug\> there, with the slug of the folder, and opens the draft when the branch first holds a commit. The job rebases the branch, runs a step for each task group that has an unticked task, regenerates the documentation, archives the change, runs the scoped checks (the pre-push stage of the hooks, the ci rows constructs, docs and openspec, and the tests of the changed files, with a fix step for a failed check), pushes, sets the title and the body of the pull request (the title of the issue, and a body that closes it), watches the checks, runs one fix step for a failed check, and marks the pull request ready. A step that fails stops the item: the job comments why and shows the masked diff of the discarded work, sets the Status to Blocked, and the Service runs the item again only after a comment 'implement: retry' or one time for each new runner image. The job leaves out an item that an agent or a person claimed with a label owner/agent or owner/human. When one claims an item that a running job works on, the job ends it at the next group boundary, with no push and no pull request. The job never merges. --confirm runs steps only when the setting roadmap.implement.in_runner is true, which only the pod of a runner Job sets: the shell of the agent is no security boundary. On a workstation, --item \<n\> --confirm starts that runner Job for the item, with the code of devops k8s run-job --template runner, and follows its log (--no-wait prints the Job's name). It refuses an item that an agent or a person claimed, an item that is neither Ready nor Planned, and a repository that has a runner Job that has not ended. --dry-run --item \<n\> prints the Job and makes no request.**

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

## `devops roadmap explain`

**Say, for one issue, whether the stage job and the implement job take it. For each job the answer is yes, or no with the reason of the first rule that fails: the issue is closed or is no item, the filter, the rules of the job (the Status, the owner, the stop on record, the plan and the branch), and the limit of a run. The reasons are the texts of the 'Left out' list of stage --plan and implement --plan. The command reads GitHub and git, calls no model and writes nothing. It uses the filter and the limit that the Service uses for each job. A group over the step budget shows only when an earlier run recorded it.**

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
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |

---

## `devops roadmap inbox`

**List what waits for a person, each line with its number, its age and the one command or action that clears it. The order is: ready plan pull requests of the jobs (G1), ready implementation pull requests of the jobs (G2), the open release pull request (G3), items in status/blocked with their cause, claims with no activity for 7 days, and labels of .github/labels.yml that the repository lacks. A second list holds the other open pull requests, those of people and agents, with drafts marked. The age is the time since the last update. A draft of a job and a pull request that a runner Job holds are not listed. The command reads the open issues, the open pull requests, the labels and the labels file, and the newest commit of that file when the labels differ. A run sends 5 requests, or 6 when the labels differ, and one more for each 100 open issues and pull requests. It calls no model and writes nothing. It leaves out an image digest that is not rolled yet: run devops argo cd apps status devops.**

```bash
devops roadmap inbox [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--dry-run` | `boolean` | - | Make no request: print the reads that a run makes, in order, with placeholders. |

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

**Score the stage job on its golden set, the plans of 2026-11-01 with their known defects. For each case the job plans from the issue text, with the checks it runs in a Job. The command prints, for each type of defect that a gate catches, how often the first reply of the model avoids it, and a total score. It stores the report as JSON under the data directory. It calls the model through the gateway, one call per case at least. With --replay it calls no model: it runs the recorded plans through the gates and exits 1 when a gate stops refusing a known-bad plan or refuses a good plan. A change to the stage prompt or to the checks states this score before and after.**

```bash
devops roadmap eval stage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--case` | `string` | - | Run only this case, by folder name or issue number. Repeat the option for more cases. |
| `--model` | `string` | - | Model for the analysis task. Without it, the configured model. |
| `--limit` | `integer` | - | Run at most this many cases, the first ones of the set. |
| `--json` | `boolean` | - | Print the report as JSON in place of the table. |
| `--dry-run` | `boolean` | - | Make no request: list the cases and the model calls that a run makes. |
| `--replay` | `boolean` | - | Make no model call. Run the recorded plans through the gates and report which known defects each gate catches. |
| `--cases` | `path` | - | Folder of the cases. Default: tests/fixtures/roadmap_eval/stage. |
| `--source` | `path` | - | Repository that holds the staging commits of the cases. Default: this checkout. |

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

---
