# Design

## Decisions

- **The command is `devops roadmap plan-recheck`, and it reads `origin/<default branch>` with git.**: The question is about the default branch, so the pass reads the tree of that branch and not the working tree. `plan-check` reads a pull request head the same way.
- **The first rule that holds gives the result: closed issue, then delivered, then a failed check, then a possible rewrite.**: A closed issue needs no other judgment. A delivered plan needs no check of its text.
- **A plan is `delivered` when it marks at least one file `(new)` and every such file is on the default branch.**: The pass reads the marks with `created_paths` and not with `read_change`, because `read_change` refuses some hand-written layouts, such as the plan of #3236. A plan with only some of its files on the branch is not delivered.
- **`rewrite` means that the plan passes the reader, `check_proposal` and `openspec validate`, and has no `design.md` or no `Verification:` line.**: The pass reports only what it can prove. A missing `design.md` is supplied as an empty stub for the check. A folder has a `Verification:` line when any group has one, as the issue counts it.
- **A plan that does not read, or fails a gate, is `new-plan`, and its first problem is its reason.**: The pass cannot tell a sample path from a stale path, so it does not call a path problem a rewrite. The second issue can narrow this.
- **The first run on the default branch finds no `rewrite` folder (2026-11-05, with #3545 applied).**: A plan with no `Verification:` line fails the reader, because a group needs a `verify` or a `process`. So it is `new-plan` and its reason says so. Issue #3556 applies the rewrite in memory and calls a plan `rewrite` when it then passes every check.
- **The folders of closed issues are in the report and in no count.**: The counts say how many live plans a gate strands.
- **The command writes nothing and has no `--confirm`.**: The issue puts the rewrite and the leave-out in a second issue, which adds the write.
- **The pass relies on #3482 for the reader.**: `read_change` must raise only `PlanReadError`. The pass does not catch `ValidationError`, so no error is hidden.

## Rejected alternatives

- **Write the rewrite and the leave-out in this change.**: The issue puts them after #3393 and allows a second issue. `src/devops_cli/roadmap/implement_amend.py` shows that a rewrite of a plan is its own change with its own tests.
- **Read the working tree of the clone.**: A worktree on a topic branch holds folders that are not on the default branch, so the report would name plans that are not merged.
- **Call a plan `rewrite` when any group lacks a `Verification:` line.**: `process` groups hold no command by design, so such a plan is not at fault. The issue counts the folders with no line at all.
