# Design

## Decisions

- **The check runs in `_exit_failure`, after the stage and before the test and static checks.**: A fix step that edited another path has failed, whatever the later checks say. An early stop spends no command run on work that is discarded.
- **The plan names a path in a code span of any group.**: `stray_files` uses the same rule. It holds the `Reads:` line and the `Changes:` line that the issue names, and also a plan that the stage job wrote with no such line. A rule on `Changes:` alone would stop every fix step of a plan with no such line.
- **The change folder is always allowed.**: A fix step runs after the archive, so the folder of the change is in `openspec/changes/archive/`. A repair of a check on the change files stays inside the plan.
- **The new class `outside_plan` has the action `wait`.**: The cause is a decision of a person: change the plan, or accept the edit. `retry` or `repair` would run the same fix again. `plan_defect` has the action `amend`, which edits a group of the plan, and that is not the remedy for a check whose cause lies in code that the plan did not list.
- **The failure has no repair paths.**: An extra turn would give the model one more try at the same edit.
- **A deleted or renamed path counts.**: `git diff --name-only --no-renames` lists the old path of a rename and the deleted path, so a fix step cannot remove a file outside the plan.
- **A group step is not checked.**: The plan names the files of a group, and #3092 keeps the stray rule for them. The issue is about the fix step.

## Rejected alternatives

- **Return the item to `New` on a stop.**: `devops roadmap return` drops the pull request and the work. The existing stop keeps the branch, comments the evidence and leaves the item Blocked with the action `wait`. A person can then decide with the work in view.
- **Check only the `changes` paths.**: The title of the issue says "the paths that the plan names", and the proposed solution lists `changes` and `reads`. The code spans of the text hold both.
- **Check the paths in the prompt only.**: A prompt is a request, and the model said it was done after changing nothing (#2116). The step must judge the exit, not the model.
