# The inbox

`devops roadmap inbox` lists what waits for a person. It shows the three gates of [the roadmap workflow](../ROADMAP_WORKFLOW.md) and the state that needs a person. The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## Which repositories it reads

Without `--repo`, the inbox reads each repository of the setting `service.repos`, in its order, and lists the lines of each. With `--repo`, it reads that repository only. When `service.repos` is empty and `--repo` is not given, the command fails and names the setting. An entry that is not `owner/name` makes the command fail before it reads any repository, and the error names the entry.

## What the inbox lists

Each line has its number, its age and the one command or action that clears it. The age is the time since the last update. A line whose age is over `roadmap.inbox.wait_days` ends with the mark `(over N days)`. After its title, the output starts with the count of the lines of each class, for example `Counts by class: refine 2, split 1.`

The lines come in this order of classes:

1. Ready plan pull requests of the jobs (G1), class `plan`.
2. Ready implementation pull requests of the jobs (G2), class `implement`.
3. The open release pull request (G3), class `release`.
4. Items in `status/blocked`, with their cause, class `blocked`.
5. New items that wait on a person in refine, one line for each, class `refine`. The line comes from the job record: the last refine round left a question for a person, or the stage job returned the item twice on the same body. A reply shows in the list until the next refine round. `devops roadmap explain <number>` gives the cause.
6. New items with a split that no person has applied, one line for each, class `split`. Refine proposed the split in a comment.
7. New items whose refine round put a covering tool to a person, one line for each, class `alternatives`. The line names the tool.
8. New items whose refine job failed as often as the limit allows, one line for each, class `failed`. The line names the failed checks, the count of tries and the last error, and asks no question. An item that refine will try again has no line. A body edit makes refine try again.
9. Drafts of jobs, class `draft`. A draft of a job is listed when a check of its head commit failed in its latest run, or when it is older than `roadmap.inbox.draft_days`. An older run that a newer run of the same check replaced does not count. A newer draft with no failed check is not listed. A pull request that a runner Job holds is not listed either.
10. Claims with no activity for 7 days, class `claim`.
11. Workflow labels of the package and labels of `.github/labels.yml` that the repository lacks or holds with another color or description, class `labels`.
12. The state of the Planned queue, when the count of Planned items is at `roadmap.stage.planned_limit`, class `queue`. The stage job then plans only items with the priority `P0-Critical` or `P1-High`. The line has no number and no age.

A second list holds the other open pull requests, those of people and agents, class `person`. It marks the drafts.

The inbox leaves out an image digest that is not rolled yet. To read it, run `devops argo cd apps status devops`.

## How to filter and count the lines

The option `--kind <class>` keeps the lines of one class, for example `--kind split`. The counts at the top stay complete. An unknown class is a usage error that names the classes.

## Settings

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| `roadmap.inbox.draft_days` | 7 | The age in days from which a draft of a job is listed, when no check of its head commit failed in its latest run. |
| `roadmap.inbox.wait_days` | 7 | The age in days from which a line is marked as old. |

## What the inbox reads

The command reads, for each repository it lists, the open issues, the open pull requests, the labels of the repository, and the labels file. It reads the newest commit of the labels file only when the labels differ. It reads the check runs of the head commit of each open draft of a job, one read for each draft. It reads no closed issue. It calls no model and writes nothing.

A run sends these requests for each repository:

| Read | Requests |
| :--- | :--- |
| The open issues. GitHub lists open pull requests here too. | One for each 100 |
| The open pull requests | One for each 100 |
| The labels of the repository | One for each 100 |
| `.github/labels.yml` on the default branch | One |
| The newest commit that changed `.github/labels.yml` | One, only when the labels differ |
| The check runs of the head commit of each open draft of a job | One for each draft |

`--dry-run` makes no request and lists these reads for each repository.

## Where the rules are

[roadmap-inbox](../../openspec/specs/roadmap-inbox/spec.md) holds the order of the lines, the line format, the age of a claim, the second list, the drafts, the splits, the alternatives, the marks, the counts, the class filter and the bound on the reads.
