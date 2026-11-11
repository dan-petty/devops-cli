# The implement job

`devops roadmap implement` implements a Staged or Planned item in bounded steps. It is steps 4 to 6 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

The command has two forms:

- With `--group`, it runs one **step**: one task group of the change of an item, in the checkout that `--source` names.
- Without `--group`, it is the **job**. It takes items and runs the steps of each item.

## A step

The agent of a step is the Coder of pydantic-ai. It runs on the tiers of the ladder of its class. A group is the class `edit`, and a fix step is the class `repair`. The setting `roadmap.implement.ladder` maps each class to a list of tiers, weakest first. The default is the local gateway group `devops-coder`. The example ConfigMap of the Service names the hosted group `deepseek-v4.1-flash-1017` as the one tier of every class, and as the model of the task `ai.tasks.implement`, so the prompts of a step leave the cluster (`k8s/README.md`, Roadmap service, item 19).

A tier is a local gateway group, a hosted group that the setting names, or an `ollama:<tag>` model. A local tier goes to the configured gateway whatever `ai.provider` is, so it never reaches a hosted provider. The command reads the gateway health of the tiers before an attempt and skips a tier that the gateway reports unhealthy. A run that ends on a provider error, or on a failure class that selects `change_tier` such as `parser`, moves the step to the next tier and spends no repair round. A repair round stays on its tier. The report names every tier that the step attempted, and the run record holds the requests and tokens of each tier.

The provider can fail inside a stream when it cannot read a tool call of the model, for example a long file in one call (class `parser`). The failure is the same for the same conversation, so the step sends the request again with one more message that asks for a smaller edit. It asks once on each tier. The next failure of this kind on the same tier ends the turn: the step moves to the next tier when the ladder holds one, and stops with class `parser` when it does not. The `wip:` commits of the tasks that passed their verification stay in the branch.

**Inputs.** The agent gets these inputs:

- The `AGENTS.md` of the checkout.
- The sections of the documents that `AGENTS.md` routes the group to. A test file brings `docs/TESTING.md`.
- The title, the problem and the acceptance criteria of the item. The criteria hold each `Requirement:` section that refine writes, with its scenarios. The step removes the HTML comments of the body, such as the markers of the jobs.
- The proposal, the design and the tasks of the change.
- The group, and the files that the group names.

The command refuses to start when the inputs do not fit the window of the task, or when the checkout has uncommitted changes.

**The shell.** The shell of the agent, the tool `run_command`, runs only `git`, `uv`, `ruff` and `mypy`, with a scratch home. A call waits until its command ends, up to `roadmap.implement.command_timeout_seconds`, so the agent has no log to poll (#4493). [The shell of a step](../ROADMAP_WORKFLOW.md#the-shell-of-a-step) lists the programs.

**Exit checks.** When the agent returns, the command runs these checks:

- The verification commands of the group. Their output is kept for the comment of the pull request.
- For a behavior group, one of its new tests fails in its call phase on the base commit of the group. The command replays the test files that the step changed, with the tests of the checkout overlaid. A test that passes there, or that stops with an error there before its assertion runs, stops the step.
- `ruff` on the changed Python files.
- `mypy` on the changed files that the type check of `devops ci` covers: the files under `src`, with its options.
- The agent made no commit, and removed or renamed no test that existed at the start of the step, except a test that the `proposal.md` on the default branch records in `## Weakened checks` (#3490).

Before these checks, the command unstages and deletes each new file that the group does not name and that is outside `src`, `tests`, `docs` and `openspec`. Such a file is an untracked file that git does not ignore, or a file that the agent staged. A fix step applies the same rule. The report lists those files.

The command writes the tasks file back to its text before the run and keeps only the ticks of the group, so no edit of that file stops the step. It then runs the pre-commit stage of the hooks of the repository on the staged changes. When the hooks pass, the command ticks every task of the group in the tasks file, also a task that the agent did not tick, and stages the file. So a missing tick does not stop the step.

**Repair.** An agent whose `ruff`, `mypy` or hook fails gets more turns. The setting `roadmap.implement.repair_rounds` bounds them. The turns may change only the files that the agent changed. A step that used all its rounds says so in its reason. A group that changed no file gets no round. A behavior group whose tests pass on the base commit, or stop with an error there, gets a turn that may change only its test files. A behavior group that changed no test file gets no round.

**Budgets.** A step stops before a model request when it has spent `roadmap.implement.step_token_budget`, `item_token_budget`, `step_time_limit_seconds` or `item_time_limit_seconds`. The stop has the class `limit_reached`, and its reason names the setting and its value. A step that reaches its token budget gets one extension of half the budget, up to `step_token_ceiling`, when its last 20 tool calls hold at least 1 successful edit and at most 3 refused commands (the rule `implement.extension`). The outcome holds the extension and its counts. The trace holds one `attempt` event for each attempt.

**Result.** When every check passes, the command commits the checkout as `<type>(<scope>): <group title> (#<item>)`. The type and the scope are those of the item title, and the title falls back to `chore` when the item title has no Conventional Commit type. Otherwise it resets the checkout to the commit where the step started. It reports the step as stopped, with the reason and the masked diff of the work it discarded, and exits 1.

The comment of the pull request holds one line for the replay of each behavior group, with its result on the base commit and the tests that failed there. A group of kind `other` shows the masked output of each verify command. The trace holds one check event for each replay, with its exit status.

A step writes nothing to GitHub.

## The job

The job takes each Staged or Planned item that a label filter names. The default filter is `status=ready` and `status=planned`.

The effort of an item picks its pass: the job runs one pass for each value of the setting `roadmap.implement.effort`, in its order. The default is `low` and then `medium`. The first pass that takes an item supplies the run, so a medium-effort item runs only when no low-effort item is selectable. An item of high effort stays out of the default set. An explicit `--filter effort=` names one pass, and the setting does not apply to that run. The run report names the pass, and `devops roadmap explain` names the effort set and whether the fallback pass applies to an item. `--item` takes one item that is Staged or Planned, and ignores the filter and the limit.

The job leaves out a Planned item whose title has no Conventional Commit type, or whose title summary has more than 60 characters. It judges the title before it reads the plan or makes a model request. `devops roadmap retitle` shortens a long summary and corrects a title type that the branch types do not list (see [the retitle job](intake.md#the-retitle-job)).

The job also leaves out an item whose plan fails the stage gates, or whose plan the reader cannot read. The job checks a Staged item on its branch, and a Planned item on the default branch. The job names the first problem in the report and in `devops roadmap explain`. No runner Job starts for such an item. The job also leaves out a Staged item while its draft holds the label `plan/needs-fix`, which the review of the stage job sets on a plan with an open finding. The reason names the label and the pull request. The Service logs such an item once for each draft and records the draft in `implement.needs_fix`. When the label is gone, the job takes the item again. A run lists the files of the default branch and reads its base specs one time. The job gives them to the check of every item. The check lists the branch of each Staged item for that item.

- A **Staged** item has its staged branch and draft on `origin`.
- A **Planned** item has its change folder on the default branch and no branch. The job makes the branch `<type>/<issue>-<slug>` there, with the slug of the folder. It opens the draft when the branch first holds a commit.

For each item, the job does these things in order:

1. It rebases the branch. A conflict stops the item with the class `conflict`. A rebase that git does not start, as in a checkout that holds changes, is no conflict: the job runs no abort, and the stop has the class `ci_infra`.
2. It runs a step for each task group that has an unticked task.
3. It regenerates the documentation and archives the change, each step only where the default branch of the target declares it in `.devops/roadmap.toml` (`[implement.steps]` with `docs = true` and `archive = true`). The Job reads the file from the default branch, so an edit of the checkout adds or removes no step. A default branch with no file declares no step. A step that the Job skips has a line in its comment on the pull request. devops-cli declares both steps.
4. It runs the scoped checks: the pre-push stage of the hooks, the `devops ci` rows `constructs`, `docs` and `openspec`, and the tests that cover the changed files. A failed check gets a fix step. A stop here still pushes the commits that passed, and the draft stays a draft.
5. It pushes.
6. It sets the title and the body of the pull request: the title of the issue, and a body that `build_body` of `pull_form` builds. The body is the Why of the archived proposal, the line `Closes #<issue>`, then the line `Change:` with the archived folder, or the active folder when the project declares no archive step. The job cuts no text. A Why that does not fit in the 1,000 characters, or that holds a closing keyword, gives way to the title of the issue. A body that breaks the form stops the item at the step `pull request`, before the job writes it. It adds the labels of the new title and removes the labels of the staging title that do not fit. A refused label is a comment on the pull request.
7. It watches the checks of the pull request, and runs a fix step for each failed check. The setting `roadmap.implement.repair_rounds` bounds the rounds.
8. It asks `draft_readiness` and stops with the reason on a refusal, then marks the pull request ready.

The job never merges. [Checks of the implement job](../ROADMAP_WORKFLOW.md#checks-of-the-implement-job) gives the detail of the hooks, the repair rounds and the time.

**A moved HEAD.** The shell of the agent allows `git`, so the agent can commit. A step makes the only commit, so before its exit checks the step resets a head that the agent moved with `git reset --soft`, to the start commit or to the last `wip:` commit. The reset keeps the work in the checkout, prints one line that names the moved head and the expected head, and the checks judge the work (#3575). The step stops with the class `head_moved` only when the reset fails.

**A stop.** A step that fails stops the item. The job comments why, shows a table of the steps (the step, its attempts, its tokens in and out, and its last failing command), shows the masked diff of the discarded work, and sets the Status to Blocked. The job keeps the trace of its run in `implement.trace`: each model call, tool call, check and retry, in the order of the run, with no argument, no output, no secret and no private host name. A tool call holds the digest of its argument, so a reader sees a repeated call, and a shell call holds the exit status of its command. When a long run does not fit the bound of the trace, the trace drops the oldest model events first, then the oldest of the other events, and counts them in `dropped`. It keeps the sums of the dropped events (their tokens, seconds, repair rounds and outcomes), so the totals of `devops roadmap explain` cover the whole run. The tool calls, checks, retries and attempts show what the run did, and `implement.spend` keeps the tokens of the run. Read it with `devops roadmap explain <issue> --trace`. The job keeps no Job artifact. Before the push of a stop, the job drops the files that no commit holds, such as the files of an archive that failed after it moved the change folder, so the rebase of the push finds a clean checkout. The Service runs the item again after the comment `implement: retry`. For a stop whose class a new attempt can fix, it runs the item again with no comment. This happens after a Job that ended with no result, up to `roadmap.implement.continuations_per_item` times (default 2). It also happens after a new runner image, within the limits of `roadmap.implement.digest_clears_per_class` and `roadmap.implement.digest_clears_per_item`.

**The premise of a behavior group.** Before a behavior group starts, the job checks its premise at the branch tip. It reads each task of the group that has an add verb, the word guard or check, and one name in a code span. When the branch tip defines that name, the job returns the item to New. The comment holds the task and the definition line. The job runs no step and makes no model request. It first takes back the checkpoints that it pushed (see Checkpoints). The check uses the same definition lookup as the premise check of the stage job (`src/devops_cli/roadmap/premise.py`). It reads the last commit that is not a `wip:` commit, so a guard that an earlier attempt of the same group kept is no defect. A group of another kind gets no check.

**A plan request.** A stopped step can request a bounded change of its plan in a `plan-request` block. The job judges requests of the kinds `path`, `command` and `task` with deterministic rules. The job commits an accepted amendment, records it in `tasks.md`, and runs the group again. A group whose inputs exceed the limit is split once for each item. A `premise` request returns the item to New with its evidence, after the same withdraw of the checkpoints. Other requests stop the item as a question for a person.

**Phase marks.** The job writes `implement.checked_sha` when the scoped checks pass, and `implement.published_sha` when the push or the draft is done. Each holds the head of that moment. A Job that starts at a head that a mark holds skips that phase, and a head that differs runs it again. The group mark also carries `implement.spend`, the sum of all Jobs of the item, so a continuation starts its item budget from the recorded spend. A retry by a person starts from zero spend, and a return to New clears the spend and both marks.

**The result and the stop of the earlier Job.** The job writes `implement.result` (`ready`, `stopped`, `yielded` or `returned`) as the last mark of its end, and clears it in its first record write. The Service reads it: a result of `ready`, `yielded` or `returned` is no stop, and a Job with no result keeps the class that its log gives. The first step of a run gets `implement.check_log` and `implement.conflict` of the earlier stop under the heading `# The stop of the earlier Job`. No later step gets them. The Job clears both keys in its first record write, and a clear rule of the Service keeps them for it.

**The comment on the pull request.** A run has one comment. Its first line is the marker of the job, and its second line holds the run id, that is the name of the runner Job (`manual` for a run that no Service started). The first write posts the comment, and a later write, as a repair round, changes it. The Job lists the comments once to find the comment of its run. A Job with no step to show writes no comment.

**The wait for the checks.** At each poll after the first, while a check runs, the job writes one line with the seconds waited, so the log of the Job shows that the wait goes on.

**Checkpoints.** At each group boundary the job runs these actions in this order: the claim check, the premise check, the checkpoint, then the step. The checkpoint pushes the groups that passed in this run, so a killed runner loses none (#3677). It makes no push while no group passed in this run, and none at the end boundary. A failed checkpoint goes to the log, and the job makes no more checkpoints. The job writes `implement.base` once when it starts: the sha of the branch for a Staged item, or `new` for a Planned item. A return to New first pushes that sha back with a lease (Staged), or deletes the branch with a lease and closes the draft (Planned). A withdraw that fails stops the item as Blocked.

**Claims.** The job leaves out an item that an agent or a person claimed with the label `owner/agent` or `owner/human`. When one claims an item that a running job works on, the job ends it at the next group boundary, with no push and no pull request. The groups that its checkpoints pushed stay on the branch.

## Where the job runs

`--confirm` runs steps only when the setting `roadmap.implement.in_runner` is true. Only the pod of a runner Job sets it. The shell of the agent is no security boundary.

On a workstation, `--item <n> --confirm` starts that runner Job for the item. It uses the code of `devops k8s run-job --template runner`, and follows the log of the Job. `--no-wait` prints the name of the Job. The command refuses these cases:

- An item that an agent or a person claimed.
- An item that is neither Ready nor Planned.
- A repository that has a runner Job that has not ended.

`--dry-run --item <n>` prints the Job and makes no request.

## Where the rules are

| Topic | Spec |
| :--- | :--- |
| The job: the filter, the order, the steps, the stop, the record | [roadmap-implement-job](../../openspec/specs/roadmap-implement-job/spec.md) |
| One step: the inputs, the exit checks, the repair, the shell | [roadmap-implement-step](../../openspec/specs/roadmap-implement-step/spec.md) |
| The runner Job, its image and its policy | [roadmap-implement-runner](../../openspec/specs/roadmap-implement-runner/spec.md) |
| Claims | [roadmap-item-claim](../../openspec/specs/roadmap-item-claim/spec.md) |
| The score of the job | [roadmap-eval-implement](../../openspec/specs/roadmap-eval-implement/spec.md) |
