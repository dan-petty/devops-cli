# Proposal: #4957

## Why
The final push of the implement Job does not fetch and rebase immediately before the push. The pushed head can miss commits that the default branch receives while scoped checks run. This breaks the requirement that every push to GitHub holds the current default branch and merges with no conflict.

## What Changes
In `ImplementRun._push`:
- After the scoped checks pass, call `self._current_tip(in_step=False)`.
- If the rebase encounters a conflict, stop the item with `push=False` and push nothing.
- Push the tip that holds the current default branch and record `published_sha`.

## Capabilities
- The implement Job rebases onto the default branch after scoped checks.
- Commits added to the default branch while scoped checks run are held in the pushed head.
- Conflicts that occur during the final rebase stop the job cleanly with no push.

## Impact
- Implement pull requests hold the latest default branch at every final push.
- Merge conflicts on GitHub pull requests from moves during scoped checks are prevented.

## Feasibility
- Verified in unit tests where the default branch advances during scoped checks.
- Verified that rebase conflicts abort cleanly and push nothing.

## Existing Tool Considered
- None found. This is internal pipeline coordination in `devops-cli`.
