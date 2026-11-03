# Design

## Decisions

- **Compare the plan's base commit (`StagePlan.sha`) with the fetched default branch.**: The planner reads the checkout and the context at that commit, so a later commit on the default branch is what the reviewer has not seen. The branch starts from the default branch that `add_worktree` fetches at write time, so the comparison also covers a commit that landed while the model planned.
- **Take the union of `reads` and `changes` of every group of the plan, and leave out `creates`.**: `creates` is a subset of `changes` by the schema of `StageGroup`, so it adds no path.
- **Fetch the default branch once in `apply_stage`, before it writes a staged item.**: The clone can lag the remote, and a stale comparison would hide a commit that moved a named path. One fetch per run keeps `plan_stage` free of a write to git.
- **Run one `git log` over all named paths, with `--name-only`, and keep the entries for those paths.**: One local command gives the commits, their subjects and their files, and the log itself makes no network call and no model call.
- **Write the moved paths in the comment of the staged item, under their own heading.**: The comment is the record the reviewer reads, and the pull request body has an 800-character limit.
- **Add the precondition rule to `feasibility` in the stage prompt, and add no reply field.**: `feasibility` is already a list of strings, and a structured field would change the reply schema and the validator for one prompt rule.

## Rejected alternatives

- **Put the moved-file list in the draft pull request body.**: `src/devops_cli/roadmap/stage_change.py` holds `BODY_MAX_CHARS: Final[int] = 800`, and the body is the squash commit message.
- **Get the commits from the GitHub API instead of the clone.**: `src/devops_cli/roadmap/clone_git.py` already gives `git()` on the clone that the job holds, so the API would add a network call and a rate limit for data that the clone holds.
- **Compare the default branch in `plan_stage`.**: `plan_stage` promises no write to git or to GitHub, and the comment is written later in `apply_stage`, so a commit that lands between the plan and the write would be missing.
- **Compare only the `reads` paths.**: `src/devops_cli/roadmap/stage_change.py` gives a group both `reads` and `changes`, and a path that the plan writes is as stale as one it reads.
- **Add a structured `preconditions` field to the stage reply.**: `StageProposal` in `src/devops_cli/roadmap/stage_change.py` already holds `feasibility` as `list[Line]`, so a new field would change the schema and the checks for one prompt rule.
