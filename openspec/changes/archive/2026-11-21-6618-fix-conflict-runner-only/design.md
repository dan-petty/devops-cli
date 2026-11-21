# Design

## Decisions

- The gate is `--confirm` in the command, as in fix-checks. The step rebases and runs tier 1 only with `confirm`.
- The clone is `ensure_checkout` in a temporary folder of the run, as fix-checks does. It holds every branch and the whole history, so the step needs no fetch. Tier 1 runs code of the pull request in this clone, and the run deletes the clone at its end. The only network call after tier 1 is the push through `OriginGit`.
- Tier 1 drops only the archive commit of the item: the commit that moves `openspec/changes/<item>-*/` away (`git show --name-status`) and holds only OpenSpec paths and generated documents. Any other conflicting commit stops the round, so tier 1 never drops work of the item.
- At a stop, tier 1 first takes the default branch for generated documents and `uv.lock`, so an archive commit that also changes a generated document is dropped too. For a file that the default branch deleted, it runs `git rm`, as a developer does.
- One function, `_round`, runs a round for the step and for the implement job: the rebase, the stops, the regeneration, the validation and the push. Its `finally` aborts the rebase and resets the branch to its tip when the round does not end `resolved`, for any error, and then writes the record with the rounds plus one. An error of git is a stop; any other error goes on after the cleanup.
- Tier 1 takes the side of the default branch by the stages of the index: `git rm` when there is no stage 2, else `git checkout --ours` and `git add`. Before each `--skip` or `--continue` it reads `REBASE_HEAD`; a call that fails and leaves it the same is a stop.
- The plan and the round use one classification of the conflicted paths (`_tier1_kind`).
- The guard before the push is `git rev-list --count origin/<default>..HEAD` > 0, so the step never pushes the tip of the default branch.

## Rejected alternatives

- A clone with `--depth=50`, deepened to the merge base: a merge of main into the branch keeps old commits of main in the range, and the loop needs plumbing for a cut that a full clone does not have.
- A content check of the result before the push: a renamed file that main edited fails it, and the stop on a failed rebase and the lease cover the cause.
- `git rebase --onto <archive>^ <archive> HEAD`: it detaches HEAD, so the branch stays where it was.
