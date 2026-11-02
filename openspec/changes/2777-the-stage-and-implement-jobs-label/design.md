# Design

## Decisions

- **The stage job adds the labels after `_open_pull` returns, outside its `except DevOpsCLIError` block.**: `_open_pull` deletes the remote branch in that block. A label failure must not delete the branch of an open pull request.
- **A label failure in the stage job is reported in the job comment on the item, and the branch and the job marks stay.**: The pull request is already open. The item is staged, and the failure is visible to a person in the comment.
- **The implement job adds the labels of the new title and removes a `type/*` or `scope/*` label that the old title gave and the new title does not give.**: The staging title is `docs(openspec)` and the delivery title has the type of the issue. A stale label would misstate the pull request.
- **The removal goes through a new `RoadmapStore.unlabel_issue`, and `pull_labels.replace_pull_labels` adds and removes in one call.**: No store method removes a label today, and both jobs need the same add-and-remove rule.

## Rejected alternatives

- **Delete the remote branch when the label call fails in the stage job.**: `_open_pull` in `src/devops_cli/roadmap/stage.py` deletes the branch only when GitHub refuses the pull request. Deleting it after the pull request is open would leave an open pull request with no branch.
- **Only add the new labels in the implement job and leave the old ones.**: The staging title is `docs(openspec)` and the delivery title carries the type of the issue, so the old `type/docs` label would stay and misstate the pull request.
- **Call `devops pr create` from the jobs.**: `openspec/changes/archive/2026-10-29-2654-roadmap-stage/design.md` records that the command works on the checked-out branch and runs `gh` in a child process, which the jobs cannot use.
