# Design

## Decisions

- **Run the plan gate in `_Judge.judge`, before `plan_implement` returns a target.** The judge runs before selection and before `apply_implement`, so a refused item never reaches a branch or a runner Job, and the selection step still writes nothing.
- **Reuse `read_change` of `plan_read.py` instead of writing a reader.** `read_change` already turns the files of a change folder into the `StageProposal` that `check_proposal` takes, and `plan_check` already uses it. One reader keeps the implement job and the plan-check command from disagreeing about one plan.
- **Read the plan at `origin/<branch>` for a Staged item and at `origin/<default>` for a Planned item.** The staged commit is what the job will implement, and a Planned item has no branch yet, so its plan is the one on the default branch. A branch prefix keeps the read off a stale local branch.
- **Read the base specs at `origin/<default>` for both kinds of item.** The spec-delta gate and the criteria gate judge the plan against the living specs, not against a branch that may hold an old copy.
- **Leave a refused item out with the first problem as its reason.** `plan_implement` selects and plans without a write to git or to GitHub, and a `LeftOut` reason already reaches `devops roadmap explain` and the implement report.
- **Leave an item out when the plan cannot be read.** `read_change` raises `PlanReadError`, and a git read raises `GitOperationError`. A broken plan is no reason to stop the other items, so the judge returns a reason and the run goes on.
- **Move the revision readers of `plan_check` to `plan_read` and make them public.** `files_at`, `file_texts_at` and `change_root` are the reads that both jobs need. A second copy in `implement.py` would let the two readers drift.

## Rejected alternatives

- **Run the plan check in `apply_implement`.** `src/devops_cli/roadmap/implement_run.py` runs `apply_implement` after the runner Job starts, so the Job and its resources are spent before the check.
- **Write a second reader in `implement.py` that joins the raw plan files to a `StageProposal`.** `read_change` already reverses `render_change`, and a second reader lets the implement job and the plan-check command disagree about one plan.
- **Write a second rule set in the implement job that reads the raw plan files.** `src/devops_cli/roadmap/stage_change.py` already holds every gate in `check_proposal`, and a second rule set lets the stage job and the implement job disagree about one plan.
- **Stop the item with a recorded failure when its plan fails the check.** A stop writes the item Status and a comment, which `src/devops_cli/roadmap/implement.py` does not do: its docstring says the module "makes no write to git or to GitHub".
- **Read the plan of a Staged item from the default branch.** A file that the staged branch adds would look missing, and `StagedTree` in `src/devops_cli/roadmap/stage_paths.py` names the files of the commit that the job will use.
- **Let a `PlanReadError` stop the run.** One broken plan would hide every later item of a round, and the report would name no reason for the item.
