# The stage job

`devops roadmap stage` makes Ready items Staged. It is step 3 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## What the job does for an item

For each item that a label filter names, the job does these things in order:

1. It makes the branch `<type>/<issue>-<slug>` at the fetched default branch. The branch keeps the type of the issue.
2. It reads the open pull requests that change a path the issue cites, and the other files that hold a metric name the issue cites. It writes the OpenSpec change of the item. The tasks are in task groups, and each group fits the step budget.
3. It makes one commit, as the identity of the session, and pushes it.
4. It opens a draft pull request. The title is `docs(openspec): plan #<issue> <summary>`. The body starts with `Plans #<issue>` and holds no closing keyword. `build_plan_body` of `pull_form` builds it, and a body that breaks the plan form goes back to the model once, as a refused plan does. It adds the `type/*` and `scope/*` labels of the title to the draft.
5. It writes one comment on the issue. The comment names the branch, the pull request, and the task groups with their measures. A label that GitHub refuses becomes a note in the comment.

The job writes each item when the item is planned, and it plans the next item after that. A stop of the Service loses at most the item in progress. Before the first plan, it removes the staged branches of closed items and writes the rejected plans of the items that the round does not select, because these need no model. It writes the rejection of a selected item after the plan of that item and before the push. It reads the paths that moved on the default branch for one item, just before its push.

The Status of the item stays Ready. The job does not mark the pull request ready. The Service does it, in its row `stage_ready`, when all checks of the draft have passed.

The overlap read is one GraphQL request for each 100 open pull requests. The context lists each pull request whose files meet a path that the item body cites, with its number, title, state, plan mark and shared paths, and each other file that holds a cited metric name. The prompt writes each entry into `## Dependencies`, and the gate refuses a plan with an empty `dependencies` field when the context lists an overlap. The comment of the staged item states the number of GraphQL requests.

The premise probe asks the staging commit about each path, class field and identifier that the issue cites, with at most `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` read-only git commands. A dotted reference such as `PullStatus.labels` is a class field when the commit defines `PullStatus`. The probe writes the file and the line of the field, or says that the class defines no such field, and it writes no path line for the reference. The plan request holds these lines, and a `feasibility` that quotes none of them is refused.

## Which items the job takes

The default filter is `status=ready`. The job takes the Ready items of any type, priority and effort, the highest priority first. `--filter` and `--limit` replace the settings `roadmap.stage.filter` and `roadmap.stage.limit` for one run, and `--item` stages one open Ready issue and ignores both.

The job leaves out an item that is not Ready, and some other items: for example an item with the label `needs-split`, an item that depends on an open issue, and an item that an agent or a person claimed. [roadmap-stage](../../openspec/specs/roadmap-stage/spec.md) holds the full list, in the requirement "The job leaves out the items it must not stage". The plan says why for each item that it leaves out. `--why` also lists the open items that the filter does not name.

## The limit on Planned items

Plans merge faster than the Service delivers them, and a plan that waits long meets a changed default branch. The setting `roadmap.stage.planned_limit` (variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT`) is the count of open Planned items at which the job plans only items with the priority `P0-Critical` or `P1-High`. The default is 20. The Service delivers about two items a day, so 20 items wait about ten days.

At the limit, the job leaves out each item with another priority, with the reason that names the setting, the count and the two priorities. An item with the priority `P0-Critical` or `P1-High` passes the limit, and so does the item that `--item` names. The limit counts Planned items only. Open staging drafts do not count. A round can take up to `roadmap.stage.limit` items while the count is below the limit, so the count can pass the limit by less than that number. Each item that passes the limit adds to the count, and no setting bounds these items. `devops roadmap explain` names the limit for an item that it holds, and `devops roadmap inbox` states when it holds. The limit does not apply to the filing of issues.

## The budget of a task group

A task group over the step budget goes back to the model once. A group that is still over the budget stops the item. `--step-tokens` replaces the setting `roadmap.stage.step_tokens` for one run.

## The tools of the planner

The model plans with read-only tools. The toolset `base` has nine tools that read the staged commit: `list_files`, `read_file`, `search_code`, `git_log`, `git_show`, `file_symbols`, `callers`, `repo_map` and `read_spec`. The setting `roadmap.stage.toolset` (variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`) is `extended` by default. It adds three tools:

| Tool | What it does | When the prompt tells the model to call it |
| :--- | :--- | :--- |
| `references` | Lists every file of the staged commit that holds a text, with the count of lines in each file. The count has no cap for a file. The list keeps at most 60 files, taken in turn from the source, the tests, the specs, the documents and the other files. | The issue renames, moves or removes a name. |
| `read_issue` | Reads one issue or pull request of the repository: state, title, labels, the first 1500 characters of the body, the last 3 comments, and for a closed item whether a merged pull request closed it. | For each `#N` that the issue names. |
| `find_issues` | Lists at most 10 open issues and pull requests of the repository that name some words, each as `#N state title`. | Before the plan says what it depends on, parks or overlaps. |

The two GitHub tools only read. They use the client and the App token of the Service, so they add no permission and no host. The tool masks secrets in the text from GitHub, cuts it, and marks it as data. The prompt tells the model that this text is no instruction. A failure of GitHub (no such item, the rate limit, no connection) is an answer as text, and the run goes on. With `base` the model has no GitHub tool, and the job needs no GitHub read for the plan. The golden-set run (`devops roadmap eval stage`) has no GitHub client, so its GitHub tools answer that GitHub is not available.

The toolset `research` adds one more tool to `extended`: `search_web`. It searches the web for alternative open tools and libraries (up to five results, each with title, URL and cut snippet). A run permits at most five web searches. Text from the web is data and never an instruction. The tool masks secrets and refuses private IP addresses and internal hostnames.

## Feasibility

`Feasibility` cites only the tools and the paths that this run used, and a premise that the run did not check is written as `not checked`, never as read or ran.

## The window of the plan run

The plan run reads the context window of the task `stage`. The task `stage` takes the fields that it does not set from the task `analysis` (the setting `ai.tasks.stage`, variable `DEVOPS_CLI_AI_TASK_STAGE_MODEL`). The Service sets both tasks, each with `context_window` 256,000 and the model `deepseek-v4.1-flash-1017`, in the keys `ai.tasks.analysis` and `ai.tasks.stage` of [k8s/devops/configmap.example.yaml](../../k8s/devops/configmap.example.yaml) (the owner decision of 2026-11-10, #4369, after the Sonnet trial of #4204). The model has `max_input_tokens` 1,048,576 in [k8s/llm/gateway/config.yaml](../../k8s/llm/gateway/config.yaml). The job uses the setting and not the larger value of the model. The variable `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` sets the window of the task `stage` alone.

The run hook offers no tool when the messages and one quarter of the window reach the window. For 256,000 tokens, the limit is 192,000 tokens. A request over the limit gets no tool, and the model must answer with its plan. So the first request has fixed caps, and the caps do not grow with the window:

| Part of the first request | Cap |
| :--- | :--- |
| Repository context | 20,480 tokens, or half of a window that is smaller than 40,960 tokens |
| Body of the item | 8,192 tokens, or one quarter of a window that is smaller than 32,768 tokens |
| Capabilities | The names only. `read_spec` gives the purpose and the requirements of one capability on demand. |

With the prompts, the first request counts about 34,000 tokens, and it leaves at least 8,192 tokens below the limit for the answers of the tools. The trace of the run records the tools that each request offered. When a run makes no tool call, the stage comment says that the run offered tools and the model chose none. A run whose tools the window ended too soon fails the item (see below).

### When the window ends the tools too soon

A plan run needs about 38,000 tokens for its first request, and many more for its tool calls: a run of 23 requests and 40 tool calls counted about 1.5 million input tokens. When the window ends the tools before the run made 8 tool calls (`CONST_ROADMAP_STAGE_MIN_TOOL_CALLS`), the model has read almost none of the code. It does not write a plan about code that it did not read: it writes the placeholder `x` in every text field, or a reply that breaks the schema. The job does not send that reply back. It fails the item at once with an error that names the settings `ai.tasks.stage.context_window` and `ai.tasks.analysis.context_window`. At 65,536 tokens, two runs made 6 and 4 calls and failed. At 262,144 tokens, a run made 40 calls and staged the item.

## The verification pass

After the checks, a model of the task `ai.tasks.verification` reviews the plan with the issue. The model is an agent: it reads the repository at the commit of the plan with the read tools of the planner, and it reads the start of the first files that the plan cites. Its request and its run use the context window of the task `verification`, and the request stays `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` below the point where the run offers no more tools. The task has no parent task, so the Service sets `context_window` 256,000 for it in the key `ai.tasks.verification` of [k8s/devops/configmap.example.yaml](../../k8s/devops/configmap.example.yaml). With no setting the task takes the default window of 32,768 tokens, which ends the tools of the run at 24,576 tokens. A review run whose tools the window ends before 8 tool calls (`CONST_ROADMAP_STAGE_MIN_TOOL_CALLS`) has read almost none of the code, so it fails the item with an error that names `ai.tasks.verification.context_window`. The item gets no draft, and the job plans the other items. A finding of the type `missing_path`, `false_premise`, `ignores_existing_code`, `task_order` or `verify_form` that quotes its evidence sends the plan back to the planner, with each open finding of the round. The evidence is a text of the issue, the plan, a cited file or a tool answer of the run. The plan goes back at most two repair rounds (`CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS`, #3039), and each round passes the checks and the review again. An open finding is a finding of one of those types, of `spec_delta_wrong` or `criterion_dropped`, or one that reports a placeholder. An open finding of the last review keeps the plan pull request a draft with the label `plan/needs-fix`. The stage comment lists those open findings first, and every other finding of each round after them. The review of refine for an item of a bot sends the same pass with no tool, and a `task_order`, `verify_form` or `criterion_dropped` finding is advice there, because a proposal has no task groups. The row `stage_ready` refuses a green draft that holds `plan/needs-fix`. A later stage round that finds no open finding removes the label, and a person may remove it too. The requirement "A verification pass follows the gates" of [roadmap-stage](../../openspec/specs/roadmap-stage/spec.md) holds the rules, and [the roadmap workflow](../ROADMAP_WORKFLOW.md#measure-the-verification-pass) tells how to score the pass.

## Failures and clean-up

An item whose model call fails is skipped and reported. The job still stages the other items, and the command then exits 1.

The Service records a failed item in its job record: the time (`stage.failed_at`), the type of the error (`stage.failed_error`), the step that failed (`stage.failed_step`, `plan` or `apply`) and the failure class (`stage.failed_class`). The class comes from the type of the error, by the one table `CLASS_BY_EXCEPTION` in `roadmap/failure.py`: a provider error is `provider`, a schema error is `parser`, a refused plan is `plan_defect`, an item that changed is `head_moved`, and any other error is `ci_infra`. The job leaves the item out for the wait of its class (`RETRY_AFTER` in `roadmap/failure.py`): 1 hour for `provider` and `ci_infra`, 6 hours for `parser` and `plan_defect`, and no time for `head_moved`. A record with no class, or a class that is unknown, waits as `ci_infra`. No setting changes the wait. The job takes the other items in the same round. The job also counts the `plan_defect` failures of an item on the same body (`stage.plan_defects`, with the hash of the body in `stage.plan_defects_body`). A body edit starts a new count, and a failure of another class leaves the count as it is. The third such failure (`CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT`) returns the item to New with one comment that lists the problems of the last plan in sequence, and clears the count. The list holds the problem of each reply that the checks refused, and then the reason of the failure, such as a stopped plan run, when the checks did not refuse the last reply. Refine gives that comment to its model when it looks at the item again. After a second return on the same body, refine waits for a reply or a body edit. `devops roadmap explain` reports the item and the time when the job takes it again. `--item` takes the item at once. A run that stages or stops the item clears the record. The row `stage` fails a round only when the round tried items and staged or stopped none, or when a failure belongs to no item, such as an outage. Three such rounds in a row on the same input suspend the row. The ledger of failed rounds keeps the class of each error across a restart of the Service, and the log line of a suspension names them. A round that the stop of the Service ends counts as `stopped`, not as an error.

The reply of the planner has no key to say that the premise of the issue is false. So a reply never returns an item to New. The job itself returns an item to New in four cases only. The plan of an open item creates a path that this item reads, the body says that a class field is absent while the staging commit defines it, a person rejected the plan (see the next section), or the item reached the limit of `plan_defect` failures on one body (`CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT`, see the paragraph above). In the second case the comment quotes the probe line with the file and the line of the field, and the job records `refine.next_step` as `edit`, so a body edit brings the item back to refine. A planner that finds an issue it cannot build as written says so in `feasibility` and plans no code that compensates for it. A person returns an item with `devops roadmap return`. A reply that breaks the schema goes back to the model once, and a second one fails the item with no comment and no change of Status.

Each run also removes the draft and the branch of a closed item, when only the identity of the session wrote to them.

## The orphan draft of a failed write

The job writes the intent mark `stage.pending` before it pushes the branch of an item. The mark is JSON with the branch name and the time. The write of the record after the draft clears it. When that write fails, or the worker dies between the push and the record, the item keeps the mark and has a pushed branch and a draft but no `stage.pr`. This is an orphan.

In each run the job judges an open item that holds the mark and no `stage.pr`. A mark younger than 1 hour is left alone, because another run can be in the middle of its publish. For an older mark the job does these things:

- When the branch of the mark is gone, it clears the record of the item.
- When only the identity of the session wrote to the branch, it closes the draft pull request that has this branch as its head, deletes the branch and clears the record. The job finds the draft with one read of the open pull requests for the round. It makes this read only when it has a pushed branch to remove. The next round plans the item again.
- When a commit past the default branch has another author, it keeps the branch, and the plan lists it.

A pushed branch with no mark is never an orphan, because a person or another agent can own it. A retitle between the failure and the next round does not matter, because the job uses the branch of the mark and not the slug of the title. A closed item that holds the mark is not judged. A bad value of the mark counts as no mark.

### The verify screen

The verify screen is the decision point `stage.verify_screen` of [ADR 0020](../adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md), before the model review of the stage job. It is pilot 1 of the decision steps of [ADR 0019](../adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md). Code builds a digest of the plan: the criteria of the issue, the groups, the paths that the repository does not hold, and whether the verify command of a group names a test file. One request asks the decision model nine yes/no questions about it, one for each defect type. The cuts of the questions are data, in `src/devops_cli/roadmap/stage/jev_screen_cuts.json`, with the model, the day and the numbers of their fit. The point has no rule, because no rule is proven on the golden set.

Two settings control the screen. `ai.decision_model` names the decision model, such as `typesafe/jev-1.14`. It is empty by default, and then the screen sends no request. `roadmap.decisions` holds the mode of the point, such as `{"stage.verify_screen": "shadow"}`. A point that is not in the mapping is `off`.

- `off`, or an empty `ai.decision_model`, sends no request and writes no record and no count. The review runs.
- `shadow` asks the decision model, and the review always runs. The screen writes one decision record, a log line that starts with `decision `, and one count of `devops_cli_decision_point_total` (point, resolver, band and mode: 8 series for this point). After the review it writes one outcome record, a log line that starts with `decision outcome `, with the same identifier: `found` when the review found an open defect, and `clean` when it found none. The join of the two records (`decision_point.join`) gives the false-clear rate of the screen and the labelled cases of the next fit.
- `on` skips the review when every probability is under its cut (the band `continue`). The bands `review` and `flag` run the review. The record of a `flag` names the questions at their flag cut.

Any error, timeout or missing answer runs the review, and the count has the resolver `fallback` and the band `none`. The screen never rejects a plan, and the review of refine always runs. Score the screen with `devops roadmap eval screen --reviewer <report>`: the report is a run of `devops roadmap eval verify` with the reviewer alone. The command fits the cuts on one half of `tests/fixtures/roadmap_eval/stage/split.json`, scores them on the other half, and repeats with the halves swapped. It prints the skipped reviews, the serious defects that the cascade loses, the false clears, the oracle (the most reviews that any screen can skip with no loss) and the cost. In the run of #4343, on the 48 cases that the reviewer could read, the oracle was 9 (19%), so no screen could meet the bar of 30% skipped reviews with no loss on that set. ADR 0020 sets the bar of the mode `on` on the shadow records. Keep the mode `shadow` or `off` until a person reads the comparison and the records.

The keys go in the ConfigMap `devops-cli-config`: `decision_model` under `ai`, and `decisions` under `roadmap`. Three images load this ConfigMap: the Service, the runner of CronJob `devops-cli-runner` and its Jobs, and Deployment `mcp-server`. The section `ai` refuses a key that it does not know, so an image of the three that is older than the key stops when it loads the settings. Thus add `ai.decision_model` only after two checks pass. First, #4397, the item that added the key, holds the `Live since` comment of its release: that comment comes when the Service and runner digests of a release that knows the key run in the cluster. Second, `kubectl -n devops exec deploy/mcp-server -- devops config get ai.decision_model` prints an empty value and no error. Then add the key and restart the Service. The section `roadmap` ignores a key that it does not know, so `roadmap.decisions` can go in at any time.

## A plan that a person rejected

A person rejects a plan when they close its pull request with no merge. The reason stays on the closed pull request, so the stage job copies it to the issue. In each run the job reads the plan pull request of each staged item. A staged item is an open New or Ready item that holds `stage.pr` and has no plan on the default branch. With `--item` the job reads the pull request of that item only. For a pull request that is closed and not merged, the job does these things in order:

1. It deletes the staged branch, when only the identity of the session wrote to it (the rule for a closed item). The delete holds only while the branch ends at the commit that the job judged. A commit that a person pushes later keeps the branch. A branch with a commit of another author stays, and the plan lists it.
2. It posts one comment on the issue. The comment holds the marker of the stage job, the marker of a rejected plan, the number of the pull request and the reason. The reason is the last comment on the pull request that a person with write access wrote and that has more than 60 characters. The comments of the Service bot and of a roadmap job do not count. A short last comment such as `rejected` does not count either: the job takes the comment before it. The job masks secrets and cuts the reason to the token cap of a reply of refine. When no comment qualifies, the comment says so.
3. It sets the Status to New and clears the stage record. It writes `stage.rejected` with the pull request, the time of the close and the files that the reason names. The record holds also the hash of the text that the plan came from (`stage.text_hash`), outside the section of refine. An item that the same run stages again keeps its Status.

The stage selection then leaves out the item, and `devops roadmap explain <number>` names the pull request. The hold ends in two cases. A person edits the text of the item, or a commit on the default branch changes a file that the reason names. An edit that a person made before the job read the closed pull request counts too. A rewrite of the section of refine does not end the hold. `--item` overrules it. A run that stages the item again clears `stage.rejected`.

Refine reads the comment as `stage_return`, because it is a comment of the stage job, and gives the item one new look. The request of the stage job holds the reason as `rejected_plan` for an item with a `stage.rejected` record. Both prompts say that the reason is the word of a person. A plan or a proposal must not state again a premise that the reason shows to be false. The row `stage_ready` cannot do this work: it reads a plan pull request until it marks it ready, and then it reads it no more.

## Modes

| Flag | What the run does |
| :--- | :--- |
| `--plan` (the default) | Reads GitHub and calls the model. It prints the changes that `--confirm` writes. It makes no GitHub write and no git write, and keeps each plan that passes the checks as one local file (see [The kept plan](#the-kept-plan)). |
| `--confirm` | Plans as `--plan` does (it reads a kept plan file when the key matches), and makes the writes in git and on GitHub for each item as soon as the item is planned. |
| `--dry-run` | Makes no request. It prints the requests and the git commands that a run makes, with placeholders. |

## The kept plan

The job keeps the plan of an item that passes the checks as the file `roadmap/stage/<owner>/<repo>/<number>.json` in the data directory. On the Service, that directory is on the volume `roadmap-service-home`. A runner pod without that volume finds no file, so each of its runs asks the planner.

- **The key.** The file holds a key: the sha256 of the item number, the title, the two hashes of the body (the text of a person and the refine section), the model name of the task `stage`, the toolset name and the prompt version. The prompt version is the sha256 of the texts of the prompts of the planner. The staged commit is not in the key.
- **A hit.** When the key is the same, the job sends the planner no request. It takes the kept plan as the first reply, and the checks and the model review run again on the current staged commit. If the new commit makes the checks refuse the plan, the plan goes back to the planner once, as a refused reply does.
- **The trace facts.** The file also holds the facts of the plan runs that made the plan: the names of the tools that they called, and the paths that they read and that the Feasibility section cites. The trace gate checks the kept plan, and each revision of it, with these facts. A file with no facts (the format of an older job) counts as a miss.
- **A miss.** When the key is new, or the file holds no facts, the job deletes the old file at once and asks the planner. The plan is written after it passes the checks and before the review, so a failed review leaves the file for the next run.
- **The end.** The job deletes the file when the item is staged. A write that fails keeps it. The golden set (`devops roadmap eval stage`) keeps no file.
- **An unreadable file.** A file that is not JSON, or that does not match the record, fails the item with an error that names the file. Remove the file, and the next run asks the planner.
- **The counter.** `devops_cli_roadmap_stage_plan_record_total` has the label `result` with 3 values: `hit`, `miss` and `written`. A miss that plans adds 1 to `miss` and 1 to `written`. The hit rate is `hit` divided by `hit` plus `miss`. Nobody has measured it yet.

## Where the rules are

[roadmap-stage](../../openspec/specs/roadmap-stage/spec.md) holds the filter, the items that the job leaves out, the branch, the commit and the draft pull request, the budget of a group, the validation of the change, the failure of one item, the `stage_ready` row, and the read-only toolbox of the planner, with its two toolsets. [roadmap-stage-eval](../../openspec/specs/roadmap-stage-eval/spec.md) holds the golden set that scores the job, and [the roadmap workflow](../ROADMAP_WORKFLOW.md#measure-the-stage-job) tells when a pull request must state the score.
