# Design

## Decisions
- **One module for the rebase.** `roadmap/phases/rebase.py` holds the rebase loop, the settle rules and `archive_commit`. implement maps its result to its own stops (`ci_infra`, `conflict`), and fix-checks to its result `stopped`. #6640 later merges the rules of fix-conflict into it.
- **`prepare` decides the rebase.** It compares the judged head with the tip that its clone read (`git merge-base --is-ancestor`). The state file holds `onto`, so a separate `publish` takes the same base. A branch that holds the tip gets no rebase, and its round pushes as before.
- **The archive stays its own commit.** The agent writes the work, the archive commit and the later commits from `onto`, as implement does, and the fix as a fourth patch. `publish` takes the branch patches only when the state names `onto`.
- **Tier 1 names its own files after a rebase.** `publish` pushes the work of the branch too, so the comment names the files that tier 1 committed, from the outcome.

## Rejected alternatives
- **Copy `_settle` into fix-checks.** The owner asked for the code of implement; a copy would make a third set of rules next to fix-conflict.
- **Keep the main-skew stop.** The rebase reads the change of the branch from the tip of main, so no failed file is main skew; the stop only moved the rebase to nobody (#6639).
- **Rebase every round.** A branch that holds the tip needs no rebase, and its round keeps the commits of the branch.
