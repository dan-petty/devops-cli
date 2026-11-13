# Design

## Decisions

- **Run the rules in `_Planner._settle`, not in the writer before the push.**: `_settle` judges each reply and owns the return path (`_Refused`) to the model. The writer runs after the planner is done, so a refusal there can only stop the item. In `_settle`, a refusal is a gate return like each other check, with the same limit, the same extension rule and the same refused-reply file.
- **Run them last, on the files that the job writes.**: The check runs after `_restored` and `openspec validate`, on the files of `render_change` that `_commit_and_push` writes. The plan reader reads back those files, so the stage job judges the plan that CI reads, and not the reply of the model. A text that the reader cannot read back is a `read` problem before the push.
- **One input form for the command and the job.**: `PlanFolder` holds the folder files, the checkout of the measure, the tree, the base specs, the issue, the budget and the registry. The command builds it from the detached worktree of the head; the job builds it from its clone at the staged commit, its tree with the folder files and its budget (`--step-tokens` or `roadmap.stage.step_tokens`). `folder_problems` and `form_problems` are the only code of these rules.
- **Leave out the rules that need the pull request.**: The check `Semantic PR title` is a check run of the pull request. A spec that moved after the plan needs a later base. An open issue in `## Dependencies` holds the merge until it closes, and the plan is right to name it; a return would push the model to drop a true dependency.
- **Return the line of the command.**: The model gets `<path>: <rule>: <message>`, the line that the CI log shows. The finding has the gate and the code `plan-check`, as `title`, `body` and `validate` have, and the log line `stage gate returns` counts it.
- **Read the folder from the worktree in the command.**: `git show` strips the end of a text. The worktree gives the files as the job wrote them, and the command already makes it for the measure.

## Rejected alternatives

- **Copy `group-no-files` into `stage.py`, as #3970 proposed.**: A copy lets the stage rule and the CI rule drift, and it covers one rule of five. The job of 2026-11-13 failed on that rule, and 4 other first pushes of the last 14 days failed on the `read` rule.
- **Run `devops roadmap plan-check` as a subprocess on the local commit before the push.**: The command needs a pull request: it reads the title, the body and the check runs from GitHub. The commit exists only in `_commit_and_push`, after the planner is done, so a refusal could not go back to the model.
- **Return a refusal for an open dependency.**: The planner can only drop the dependency to pass, and the plan then merges before the issue that it needs.
- **Run `devops ci test tests/invariants` before the push now.**: #4559 (a Job for each stage item) is open, and no first stage push failed a test check in the 14 days, so the run adds minutes to each item with no measured gain.
