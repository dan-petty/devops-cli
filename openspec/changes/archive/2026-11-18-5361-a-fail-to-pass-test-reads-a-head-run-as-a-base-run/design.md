# Design

## Decisions
- Record the base worktree when `git worktree add` makes it. The base replay tree is the worktree
  named `tree`; a head worktree (`<temp-dir>/head`) and a plain-base worktree
  (`<temp-dir>/plain_base`) are not it. The fake adds that recorded path to `base_worktrees`.
- `_ran_on_base` returns true when the call's working folder is the recorded base worktree or
  inside it, and false otherwise. A folder named `tree` that no `git worktree add` recorded is
  therefore a head run.
- Keep `base_worktrees` after `git worktree remove`, because the tests read the run's calls after
  it finishes and must still tell the base rows from the head rows.

## Rejected alternatives
- Keep the folder name `tree`: this is the defect. A checkout root named `tree` gets the base
  answer for a head run.
- Match any recorded worktree: the head worktree of `--head <revision>` is recorded too, so the
  head gate row would read as a base run.
- Run the failing test in a root under `tmp_path`: this hides the defect in one test and leaves the
  folder-name assumption for every other caller.
