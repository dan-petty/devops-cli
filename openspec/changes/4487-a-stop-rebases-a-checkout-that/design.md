# Design

## Decisions

- The stop drops what no commit holds, in `_push_passed` with `at_stop`, before `_current_tip` rebases. Every stop goes through `stop`, so a failed documentation step, a failed archive, a program that ran out of time and a scoped check that wrote a file all get a clean checkout. A drop that git refuses goes to the comment as a failed push, as any other git failure of the push does.
- The checkpoint between steps does not drop files. Every path between steps commits its work, and `run_step` refuses a checkout that is not clean (`_require_clean`), so a drop there would hide that defect.
- A rebase that git refuses to start has the class `ci_infra`: the cause is the state of the checkout of the Job, not the code of the item. A new Job starts from a new worktree, so the default action `retry` fits.

## Rejected alternatives

- Restore the checkout in `_program` when the program fails: it covers the documentation and the archive, but not a scoped check or another stop that leaves a file. The stop is the one place where every stop passes.
- Rebase a copy at a stop, as a step does (`_rebased_copy`): `_move_wip` and `_kept_note` read the local `wip:` commits, which then differ from the commits on `origin`, so the stop comment would name a sha that `origin` does not hold.
- `git rebase --autostash`: it would rebase with the files of the failed program and put them back after. They belong to no commit and no push sends them, and the stash can conflict when it is applied again.
- Read `REBASE_HEAD` to know that a rebase started: git writes it only when a rebase stops on a pick. The state directories mark every rebase in progress.
