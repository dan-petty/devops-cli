# The stage job

`devops roadmap stage` makes Ready items Staged. It is step 3 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## What the job does for an item

For each item that a label filter names, the job does these things in order:

1. It makes the branch `<type>/<issue>-<slug>` at the fetched default branch. The branch keeps the type of the issue.
2. It reads the open pull requests that change a path the issue cites, and the other files that hold a metric name the issue cites. It writes the OpenSpec change of the item. The tasks are in task groups, and each group fits the step budget.
3. It makes one commit, as the identity of the session, and pushes it.
4. It opens a draft pull request. The title is `docs(openspec): plan #<issue> <summary>`. The body starts with `Plans #<issue>` and holds no closing keyword. It adds the `type/*` and `scope/*` labels of the title to the draft.
5. It writes one comment on the issue. The comment names the branch, the pull request, and the task groups with their measures. A label that GitHub refuses becomes a note in the comment.

The Status of the item stays Ready. The job does not mark the pull request ready. The Service does it, in its row `stage_ready`, when all checks of the draft have passed.

The overlap read is one GraphQL request for each 100 open pull requests. The context lists each pull request whose files meet a path that the item body cites, with its number, title, state, plan mark and shared paths, and each other file that holds a cited metric name. The prompt writes each entry into `## Dependencies`, and the gate refuses a plan with an empty `dependencies` field when the context lists an overlap. The comment of the staged item states the number of GraphQL requests.

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

## The window of the plan run

The plan run reads the context window of the task `stage`. The task `stage` takes the fields that it does not set from the task `analysis` (the setting `ai.tasks.stage`, variable `DEVOPS_CLI_AI_TASK_STAGE_MODEL`), so the window and the model are those of `analysis` until a person sets the task `stage`. The Service sets `context_window` 65,536 for `analysis` in the key `ai.tasks.analysis` of [k8s/devops/configmap.example.yaml](../../k8s/devops/configmap.example.yaml). The model of the task, `deepseek-v4.1-flash-1017`, has `max_input_tokens` 1,048,576 in [k8s/llm/gateway/config.yaml](../../k8s/llm/gateway/config.yaml). The job uses the setting and not the larger value of the model.

The run hook offers no tool when the messages and one quarter of the window reach the window. For 65,536 tokens, the limit is 49,152 tokens. A request over the limit gets no tool, and the model writes a plan about code that it did not read. So the first request has fixed caps, and the caps do not grow with the window:

| Part of the first request | Cap |
| :--- | :--- |
| Repository context | 20,480 tokens, or half of a window that is smaller than 40,960 tokens |
| Body of the item | 8,192 tokens, or one quarter of a window that is smaller than 32,768 tokens |
| Capabilities | The names only. `read_spec` gives the purpose and the requirements of one capability on demand. |

With the prompts, the first request counts about 34,000 tokens, and it leaves at least 8,192 tokens below the limit for the answers of the tools. The trace of the run records the tools that each request offered. When a run makes no tool call, the stage comment says why: either each request reached the limit and offered no tool, or the run offered tools and the model chose none.

## The verification pass

After the checks, a model of the task `ai.tasks.verification` reviews the plan with the issue. The model is an agent: it reads the repository at the commit of the plan with the read tools of the planner, and it reads the start of the first files that the plan cites. Its request and its run use the context window of the task `verification`, and the request stays `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` below the point where the run offers no more tools. A finding of the type `missing_path`, `false_premise`, `ignores_existing_code`, `task_order` or `verify_form` that quotes its evidence sends the plan back to the planner, with each open finding of the round. The evidence is a text of the issue, the plan, a cited file or a tool answer of the run. The plan goes back at most two repair rounds (`CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS`, #3039), and each round passes the checks and the review again. An open finding is a finding of one of those types, of `spec_delta_wrong` or `criterion_dropped`, or one that reports a placeholder. An open finding of the last review keeps the plan pull request a draft with the label `plan/needs-fix`. The stage comment lists those open findings first, and every other finding of each round after them. The review of refine for an item of a bot sends the same pass with no tool, and a `task_order`, `verify_form` or `criterion_dropped` finding is advice there, because a proposal has no task groups. The row `stage_ready` refuses a green draft that holds `plan/needs-fix`. A later stage round that finds no open finding removes the label, and a person may remove it too. The requirement "A verification pass follows the gates" of [roadmap-stage](../../openspec/specs/roadmap-stage/spec.md) holds the rules, and [the roadmap workflow](../ROADMAP_WORKFLOW.md#measure-the-verification-pass) tells how to score the pass.

## Failures and clean-up

An item whose model call fails is skipped and reported. The job still stages the other items, and the command then exits 1.

The Service records a failed item in its job record: the time (`stage.failed_at`) and the class of the error (`stage.failed_error`). The job leaves the item out for `roadmap.stage.retry_hours` hours (default 6), and takes the other items in the same round. `devops roadmap explain` reports the item and the time when the job takes it again. `--item` takes the item at once. A run that stages or stops the item clears the record. The row `stage` fails a round only when the round tried items and staged or stopped none, or when a failure belongs to no item, such as an outage. Three such rounds in a row on the same input suspend the row. The ledger of failed rounds keeps the class of each error across a restart of the Service, and the log line of a suspension names them. A round that the stop of the Service ends counts as `stopped`, not as an error.

The reply of the planner has no key to say that the premise of the issue is false. So a reply never returns an item to New. The job itself returns an item to New in two cases only. The plan of an open item creates a path that this item reads, or a person rejected the plan (see the next section). A planner that finds an issue it cannot build as written says so in `feasibility` and plans no code that compensates for it. A person returns an item with `devops roadmap return`. A reply that breaks the schema goes back to the model once, and a second one fails the item with no comment and no change of Status.

Each run also removes the draft and the branch of a closed item, when only the identity of the session wrote to them.

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
| `--plan` (the default) | Reads GitHub and calls the model. It prints the changes that `--confirm` writes. It writes nothing. |
| `--confirm` | Plans as `--plan` does, then makes the writes in git and on GitHub. |
| `--dry-run` | Makes no request. It prints the requests and the git commands that a run makes, with placeholders. |

## Where the rules are

[roadmap-stage](../../openspec/specs/roadmap-stage/spec.md) holds the filter, the items that the job leaves out, the branch, the commit and the draft pull request, the budget of a group, the validation of the change, the failure of one item, the `stage_ready` row, and the read-only toolbox of the planner, with its two toolsets. [roadmap-stage-eval](../../openspec/specs/roadmap-stage-eval/spec.md) holds the golden set that scores the job, and [the roadmap workflow](../ROADMAP_WORKFLOW.md#measure-the-stage-job) tells when a pull request must state the score.
