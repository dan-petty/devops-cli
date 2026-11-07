# The intake job

`devops roadmap intake` turns candidates into items. It is step 1 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

## What a candidate is

A candidate is one of two things:

- An open issue that has no `priority/*` label. Intake takes every such issue, or only the issues named with `--issue`.
- A new issue that does not exist yet. A caller files it with `--title` and `--body-file`. Intake labels the new issue `source/agent` when an agent files it, which is the default of `--filed-by`. A person who passes `--filed-by person` gets no such label.

A text that looks like it holds a secret is refused.

A new candidate whose title has a Conventional Commit type and a summary of more than 60 characters is refused with `--title`. An emoji counts as two. The message names the length and the limit, and intake files no issue. The stage job and the implement job leave out an item with such a title, so the filer writes a shorter summary. `devops roadmap retitle` shortens the title of an open item that already has a long summary (see [the retitle job](#the-retitle-job)).

## What intake writes

For each candidate, intake sets these fields on GitHub:

1. A `type/*` label and a `scope/*` label, from the Conventional Commit title. The model picks the type only for a title that has no Conventional Commit type.
2. The label `status/new`.
3. A Value label and an Effort label.
4. A reason comment.
5. The `priority/*` label, last. The item then goes to the backlog.

A label that a person set stays. Intake sets no milestone, because a person plans the milestones. A milestone that an issue has stays.

## Duplicates

The model compares each candidate with the items and with the issues that a person closed as not planned. It does not compare a candidate with an issue that has sub-issues, because the sub-issues deliver that issue.

The model can name a possible duplicate. Intake then places the candidate as usual, and the report and the reason comment name the possible original for a person to close. Intake never closes an issue and never drops a candidate. This holds for a new candidate too: intake files it even when it is a possible duplicate.

A run can stop after it filed a new candidate. The next run finds the open issue that has the same title and body, and places that issue. It files no second issue.

To keep an issue off the roadmap, close it as not planned:

```text
devops gh issues close <number> --reason not-planned
```

## The three modes

| Flag | What the run does |
| :--- | :--- |
| `--dry-run` | Makes no request to GitHub or to a model. It prints the requests that a run makes. |
| `--plan` (the default) | Reads GitHub and calls the model. It writes nothing. It prints each planned change and what the run spent. |
| `--confirm` | Plans as `--plan` does, then makes the writes. |

## The retitle job

`devops roadmap retitle` shortens the title summary of open items that has more than 60 characters. The stage job and the implement job leave out such an item, and the check `Semantic PR title` refuses its delivery title.

- It takes the open items with a Conventional Commit type, the lowest number first, at most `--limit` (25) in a run. `--item` names one item.
- It keeps the type and the scope and writes only the summary. The new title passes `title_problems` of `src/devops_cli/roadmap/pull_form.py`.
- A Planned item takes the summary of the title of its plan pull request (`plan #<issue> <summary>`), which its job record names. The job makes no model call for it. When that title gives no valid summary, the job leaves the item and comments the reason once.
- Another item gets one request to the `triage` model, and one more with the faults of the first reply. A reply that fails twice leaves the item.
- It leaves a title that someone changed after the last comment of a job. It reads the title changes on the timeline of the item.
- When it leaves an item, it writes the mark `retitle.skipped` once. The value is a hash of the title, the body and the `stage.pr` mark. The selection leaves the item out while the hash holds, so a later round reads nothing of it and makes no model request for it. A change to the title, the body or `stage.pr` selects it again. A comment does not.
- Without `--confirm` it prints the new titles and writes nothing. With `--confirm` it writes each title and one comment with the marker `<!-- devops roadmap retitle -->`. `--dry-run` makes no request.
- The Service runs the job as the row `retitle` of the model lane. The row is due on a first run and every 61 minutes. It runs after `refine` and before `stage`, so the stage job reads the new titles in the same round. Each run takes at most 25 items and writes as `--confirm` does. The row needs no clone.

## Where the rules are

| Topic | Spec |
| :--- | :--- |
| Duplicate verdict, report lines, no close, retry of a stopped run, the source of a part | [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
| Type and scope labels from the title | [roadmap-intake-title-labels](../../openspec/specs/roadmap-intake-title-labels/spec.md) |
| The reply of the model | [roadmap-intake-reply-schema](../../openspec/specs/roadmap-intake-reply-schema/spec.md) |
| Intake of one issue on an `issues` event of GitHub | [roadmap-scoped-updates](../../openspec/specs/roadmap-scoped-updates/spec.md) |
| The evaluation of the duplicate verdict | `devops roadmap eval intake`, in [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
