# The inbox

`devops roadmap inbox` lists what waits for a person. It shows the three gates of [the roadmap workflow](../ROADMAP_WORKFLOW.md) and the state that needs a person. The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## What the inbox lists

Each line has its number, its age and the one command or action that clears it. The age is the time since the last update. The first list has these kinds of line, in this order:

1. Ready plan pull requests of the jobs (G1).
2. Ready implementation pull requests of the jobs (G2).
3. The open release pull request (G3).
4. Items in `status/blocked`, with their cause.
5. New items that wait on a person in refine, one line for each. The line comes from the job record: the last refine round left a question for a person, or the stage job returned the item twice on the same body. A reply shows in the list until the next refine round. `devops roadmap explain <number>` gives the cause.
6. Claims with no activity for 7 days.
7. Labels of `.github/labels.yml` that the repository lacks.

A second list holds the other open pull requests, those of people and agents. It marks the drafts.

A draft of a job is not listed. A pull request that a runner Job holds is not listed either.

The inbox leaves out an image digest that is not rolled yet. To read it, run `devops argo cd apps status devops`.

## What the inbox reads

The command reads the open issues, the open pull requests, the labels of the repository, and the labels file. It reads the newest commit of the labels file only when the labels differ. It reads no closed issue. It calls no model and writes nothing.

A run sends these requests:

| Read | Requests |
| :--- | :--- |
| The open issues. GitHub lists open pull requests here too. | One for each 100 |
| The open pull requests | One for each 100 |
| The labels of the repository | One for each 100 |
| `.github/labels.yml` on the default branch | One |
| The newest commit that changed `.github/labels.yml` | One, only when the labels differ |

`--dry-run` makes no request and lists these reads.

## Where the rules are

[roadmap-inbox](../../openspec/specs/roadmap-inbox/spec.md) holds the order of the lines, the line format, the age of a claim, the second list, and the bound on the reads.
