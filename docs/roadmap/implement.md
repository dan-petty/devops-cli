# The implement job

`devops roadmap implement` implements a Staged or Planned item in bounded steps. It is steps 4 to 6 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

The command has two forms:

- With `--group`, it runs one **step**: one task group of the change of an item, in the checkout that `--source` names.
- Without `--group`, it is the **job**. It takes items and runs the steps of each item.

## A step

The agent of a step is the Coder of pydantic-ai. It runs on the model of the task `ai.tasks.implement`.

**Inputs.** The agent gets these inputs:

- The `AGENTS.md` of the checkout.
- The sections of the documents that `AGENTS.md` routes the group to. A test file brings `docs/TESTING.md`.
- The title, the problem and the acceptance criteria of the item.
- The proposal, the design and the tasks of the change.
- The group, and the files that the group names.

The command refuses to start when the inputs do not fit the window of the task, or when the checkout has uncommitted changes.

**The shell.** The shell of the agent runs only `git`, `uv`, `ruff` and `mypy`, with a scratch home. [The shell of a step](../ROADMAP_WORKFLOW.md#the-shell-of-a-step) lists the programs.

**Exit checks.** When the agent returns, the command runs these checks:

- The verification commands of the group.
- `ruff` on the changed Python files.
- `mypy` on the changed files that the type check of `devops ci` covers: the files under `src`, with its options.
- The agent made no commit, and removed or renamed no test that existed at the start of the step.
- The agent ticked every task of the group.

Before these checks, the command deletes each new file that git does not ignore, that the group does not name, and that is outside `src`, `tests`, `docs` and `openspec`. The report lists those files.

The command writes the tasks file back to its text before the run and keeps only the ticks of the group, so no edit of that file stops the step. It then runs the pre-commit stage of the hooks of the repository on the staged changes.

**Repair.** An agent whose `ruff`, `mypy` or hook fails, or that forgets a tick, gets more turns. The setting `roadmap.implement.repair_rounds` bounds them. The turns may change only the files that the agent changed.

**Result.** When every check passes, the command commits the checkout as `<group title> (#<item>)`. Otherwise it resets the checkout to the commit where the step started. It reports the step as stopped, with the reason and the masked diff of the work it discarded, and exits 1.

A step writes nothing to GitHub.

## The job

The job takes each Staged or Planned item that a label filter names. The default filter is `status=ready`, `status=planned` and `effort=low`. `--item` takes one item that is Staged or Planned, and ignores the filter and the limit.

- A **Staged** item has its staged branch and draft on `origin`.
- A **Planned** item has its change folder on the default branch and no branch. The job makes the branch `<type>/<issue>-<slug>` there, with the slug of the folder. It opens the draft when the branch first holds a commit.

For each item, the job does these things in order:

1. It rebases the branch.
2. It runs a step for each task group that has an unticked task.
3. It regenerates the documentation and archives the change.
4. It runs the scoped checks: the pre-push stage of the hooks, the `devops ci` rows `constructs`, `docs` and `openspec`, and the tests that cover the changed files. A failed check gets a fix step.
5. It pushes.
6. It sets the title and the body of the pull request: the title of the issue, and a body that closes it.
7. It watches the checks of the pull request, and runs a fix step for each failed check. The setting `roadmap.implement.repair_rounds` bounds the rounds.
8. It marks the pull request ready.

The job never merges. [Checks of the implement job](../ROADMAP_WORKFLOW.md#checks-of-the-implement-job) gives the detail of the hooks, the repair rounds and the time.

**A stop.** A step that fails stops the item. The job comments why, shows the masked diff of the discarded work, and sets the Status to Blocked. The Service runs the item again only after the comment `implement: retry`, or one time for each new runner image.

**Claims.** The job leaves out an item that an agent or a person claimed with the label `owner/agent` or `owner/human`. When one claims an item that a running job works on, the job ends it at the next group boundary, with no push and no pull request.

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
