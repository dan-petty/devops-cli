# The golden set of the stage job

One folder for each plan that the stage job staged. `devops roadmap eval stage` reads them. The code that loads them is `src/devops_cli/roadmap/stage_eval_cases.py`, and the use is in [docs/ROADMAP_WORKFLOW.md](../../../../docs/ROADMAP_WORKFLOW.md).

| File | Holds |
| :--- | :--- |
| `case.json` | The pull request, the merge commit, the commit the plan was staged on, the verdict and scores of the review, and the defects with their evidence |
| `issue.md` | The body of the issue |
| `plan.json` | The plan as a `StageProposal`, with the groups as the model wrote them |
| `facts.json` | The tracked files of the staged commit that the gates need, and the capabilities the plan names that have a spec |

How the cases were made (2026-11-01):

- The 37 folders with a pull request of the evaluation come from the review of those plans. The text of each defect and its evidence are from the review. The type of a defect is set from the text of the review. The gate of a defect is the gate that catches its type today.
- The plan is the change folder of the merge commit, read with `git show <merge>:<file>`. The commit the plan was staged on is the parent of the merge commit: the staging commit itself is not in the history after a squash.
- A plan staged before #2775 names no files in its groups. For these, `changes` lists the paths that the tasks name.
- A group has the kind `behavior` when it has a failing-test task, as every group had before #3005. The kind rule then refuses the groups that change no path under `src/`.
- `facts.json` holds the files that the plan names, the files with the same name as a missing path, and one file for each suffix and each top folder of the tree. The gate gives the same answer on these files as on the full tree. A replay needs no deep clone.
- The 3 folders that start with `good-` are the plans of #2992, #2859 and #2858 with the one wrong path corrected. They have no defect, and every gate must accept them.

The size is 160 files and about 1 MB. A case holds no secret, no private host name and no private address.
