# Design

## Decisions

- **Run the plan check in `_Judge.judge`, before `plan_implement` returns a target.**: The judge runs before selection and before `apply_implement`, so a refused item never reaches a branch or a runner Job, and the selection step still writes nothing.
- **Leave a refused item out with the first problem as its reason instead of stopping it.**: `plan_implement` selects and plans without a write to git or to GitHub, and a `LeftOut` reason already reaches `devops roadmap explain` and the implement report.
- **Read the plan of a Staged item from its branch and the plan of a Planned item from the default branch.**: The staged commit is what the job will implement, and a Planned item has no branch yet, so its plan is the one on the default branch.
- **Build a `StageProposal` from the change folder and hand it to the existing `check_proposal`.**: One gate judges the stage job and the implement job, so the two never disagree about a plan.
- **Pass the item body, the base capability names and the base requirement names to `check_proposal`.**: The criteria gate and the spec-delta gate need them, and without them those gates would skip or judge duplicates wrongly.

## Rejected alternatives

- **Run the plan check in `apply_implement`.**: `src/devops_cli/roadmap/implement_run.py` runs `apply_implement` after the runner Job starts, so the Job and its resources are spent before the check.
- **Write a second rule set in the implement job that reads the raw plan files.**: `src/devops_cli/roadmap/stage_change.py` already holds every gate in `check_proposal`, and a second rule set lets the stage job and the implement job disagree about one plan.
- **Stop the item with a recorded failure when its plan fails the check.**: A stop writes the item Status and a comment, which `src/devops_cli/roadmap/implement.py` does not do: its docstring says the module "makes no write to git or to GitHub".
- **Read the plan of a Staged item from the default branch.**: A file that the staged branch adds would look missing, and `StagedTree` in `src/devops_cli/roadmap/stage_paths.py` names the files of the commit that the job will use.
