# The plan recheck

`devops roadmap plan-recheck` judges again each change folder that the default branch holds. A plan
is judged once, when the stage job writes it. A later gate can strand an old plan. A delivered plan
can stay Planned. The folder of a closed issue stays in every count. This command shows all three.

## What it reads

The command reads `origin/<default branch>` of the model clone, or of the clone that `--source`
names. It reads each folder `openspec/changes/<issue>-<slug>/`, the open issues, and the issue of
each folder that is not open. It calls no model and writes nothing to git or to GitHub.

For each folder it runs the same checks as [plan-check](plan-check.md): the plan reader
(`read_change`), the stage gates (`check_proposal`) and `openspec validate --strict`.

## The result of a folder

Each folder gets one result. The first rule that holds gives it.

| Result | Meaning |
| :--- | :--- |
| `cleanup` | The issue of the folder is closed. Run `openspec archive`, or delete the folder. |
| `delivered` | Every file that the plan marks `(new)` is on the default branch. The issue is not closed yet. |
| `new-plan` | The plan does not read, or it fails a gate or `openspec validate`. The first line below the folder is the first problem. |
| `rewrite` | The plan passes every check, but it has no `design.md` or no `Verification:` line. A mechanical rewrite can add them. |
| `ok` | None of the above. |

A plan with no `Verification:` line usually fails the plan reader, because a group needs a command or a manual process. So the command shows such a plan as `new-plan`, with the reader error as the reason. The result `rewrite` is for a plan that passes every check and lacks only the `design.md` or the `Verification:` line.

The command does not tell a sample path from a stale path. A path that the tree lacks is a
`new-plan` problem.

## The counts

A folder of a closed issue is in no count. The report prints these counts for the other folders:

- how many folders have no `Verification:` line, so the implement step requires no plan command;
- how many folders the plan reader refuses;
- the number of folders for each result.

## Policy

A new gate on merged plans only reports until this pass has run. The pass shows which plans the
gate strands. A person then decides, for each plan, to rewrite it, to plan it again, or to clean it
up. The pass closes no issue.

| Option | What it does |
| :--- | :--- |
| `--repo <owner/name>` | The repository. Without it, the origin of the checkout. |
| `--source <path>` | The clone to read. Without it, the model clone. |
| `--json` | Print the folders and the counts as JSON. |
| `--dry-run` | Make no request: print the reads that a run makes, with placeholders. |

## Where the rules are

[roadmap-plan-recheck](../../openspec/specs/roadmap-plan-recheck/spec.md) holds the requirements.
