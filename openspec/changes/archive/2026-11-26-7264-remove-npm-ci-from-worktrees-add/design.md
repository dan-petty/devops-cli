# Design

## Decisions
- **Delete the step, keep no switch.** The cause was a stale copy on `PATH`, and it is gone. A setting that turns the install on again would keep code for a case that the image and `PATH` cover.
- **Keep the gate message.** `version_differs` of the OpenSpec gate names the path of the binary that it ran. That path shows a stale copy at once, so the documents name `which -a openspec` as the first step.
- **The archive of #7233 stays.** It is the record of that change. This change removes its requirement with a delta.

## Rejected alternatives
- **Keep the install for each worktree.** It hides a wrong `PATH`: the gate passes in the worktree, and each other user of the container still gets the stale tool.
- **Put the image copy first on `PATH` in the product code.** The devcontainer and the image own `PATH`. Product code that changes it is a second fix on a fix.
