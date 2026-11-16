# Design

## Decisions
- Call `commit_stage` inside `_commit_if_changed`:
  One call site covers the documentation commit, the archive commit, and the amendment commits.
  This avoids repeated logic across multiple commit methods.
- Check `git status --porcelain` before running hooks:
  When the checkout holds no change, do not run hooks and do not commit.
- Handle fixer rewrites:
  `commit_stage` already stages rewritten files and runs the stage once more.
  If the second run passes, `_commit_if_changed` commits the rewritten files.
- Handle hook failure:
  When `commit_stage` returns a failed run, raise `_StopError` with the hook output.
  This stops the item and shows the hook output in the stop comment.

## Rejected alternatives
- Run hooks in a git client hook:
  Rejected because the process runner gives git children the GitHub session token.
- Call hooks separately in `_generate_docs` and `_finish_change`:
  Rejected because it duplicates logic and misses amendment commits.
- Run the stage three or more times:
  Rejected because `commit_stage` already handles the rerun for fixer hooks.
