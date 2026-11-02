# The intake job

`devops roadmap intake` turns candidates into items. It is step 1 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

## What a candidate is

A candidate is one of two things:

- An open issue that has no `priority/*` label. Intake takes every such issue, or only the issues named with `--issue`.
- A new issue that does not exist yet. A caller files it with `--title` and `--body-file`. Intake labels the new issue `source/agent` when an agent files it, which is the default of `--filed-by`. A person who passes `--filed-by person` gets no such label.

A text that looks like it holds a secret is refused.

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

## Where the rules are

| Topic | Spec |
| :--- | :--- |
| Duplicate verdict, report lines, no close, retry of a stopped run, the source of a part | [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
| Type and scope labels from the title | [roadmap-intake-title-labels](../../openspec/specs/roadmap-intake-title-labels/spec.md) |
| The reply of the model | [roadmap-intake-reply-schema](../../openspec/specs/roadmap-intake-reply-schema/spec.md) |
| Intake of one issue on an `issues` event of GitHub | [roadmap-scoped-updates](../../openspec/specs/roadmap-scoped-updates/spec.md) |
| The evaluation of the duplicate verdict | `devops roadmap intake-eval`, in [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
