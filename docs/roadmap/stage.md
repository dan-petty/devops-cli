# The stage job

`devops roadmap stage` makes Ready items Staged. It is step 3 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## What the job does for an item

For each item that a label filter names, the job does these things in order:

1. It makes the branch `<type>/<issue>-<slug>` at the fetched default branch. The branch keeps the type of the issue.
2. It writes the OpenSpec change of the item. The tasks are in task groups, and each group fits the step budget.
3. It makes one commit, as the identity of the session, and pushes it.
4. It opens a draft pull request. The title is `docs(openspec): plan #<issue> <summary>`. The body starts with `Plans #<issue>` and holds no closing keyword.
5. It writes one comment on the issue. The comment names the branch, the pull request, and the task groups with their measures.

The Status of the item stays Ready. The job does not mark the pull request ready. The Service does it, in its row `stage_ready`, when all checks of the draft have passed.

## Which items the job takes

The default filter is `status=ready`. The job takes the Ready items of any type, priority and effort, the highest priority first. `--filter` and `--limit` replace the settings `roadmap.stage.filter` and `roadmap.stage.limit` for one run, and `--item` stages one open Ready issue and ignores both.

The job leaves out an item that is not Ready, and some other items: for example an item with the label `needs-split`, an item that depends on an open issue, and an item that an agent or a person claimed. [roadmap-stage](../../openspec/specs/roadmap-stage/spec.md) holds the full list, in the requirement "The job leaves out the items it must not stage". The plan says why for each item that it leaves out. `--why` also lists the open items that the filter does not name.

## The budget of a task group

A task group over the step budget goes back to the model once. A group that is still over the budget stops the item. `--step-tokens` replaces the setting `roadmap.stage.step_tokens` for one run.

## Failures and clean-up

An item whose model call fails is skipped and reported. The job still stages the other items, and the command then exits 1.

Each run also removes the draft and the branch of a closed item, when only the identity of the session wrote to them.

## Modes

| Flag | What the run does |
| :--- | :--- |
| `--plan` (the default) | Reads GitHub and calls the model. It prints the changes that `--confirm` writes. It writes nothing. |
| `--confirm` | Plans as `--plan` does, then makes the writes in git and on GitHub. |
| `--dry-run` | Makes no request. It prints the requests and the git commands that a run makes, with placeholders. |

## Where the rules are

[roadmap-stage](../../openspec/specs/roadmap-stage/spec.md) holds the filter, the items that the job leaves out, the branch, the commit and the draft pull request, the budget of a group, the validation of the change, the failure of one item, the `stage_ready` row, and the read-only toolbox of the planner. [roadmap-stage-eval](../../openspec/specs/roadmap-stage-eval/spec.md) holds the golden set that scores the job, and [the roadmap workflow](../ROADMAP_WORKFLOW.md#measure-the-stage-job) tells when a pull request must state the score.
