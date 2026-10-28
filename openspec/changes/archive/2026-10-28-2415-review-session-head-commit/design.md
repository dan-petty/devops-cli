# Design

## Decisions

### The checkout is a field of its own, not a part of the subject

`subject_key` is the digest of the subject, and review history counts one session per subject. A commit in the subject would make a second subject of the same reviewed text whenever an unrelated commit moved `HEAD`, and history would stop collapsing repeats. The checkout is a separate field of `ReviewSessionPayload`.

### The whole working tree decides "clean"

A finding is about merged code when the reviewed text is the text of the commit. The reader asks git for every change in the checkout, untracked files too, and not only for the reviewed paths. A change outside the target makes the session not count as merged code. That is the safe side: the hand-off files nothing it cannot prove, and a person can run the review again on a clean tree.

### The ancestor check runs when the hand-off asks

`origin/main` moves. A head recorded on a topic branch that later merges by fast-forward or merge commit is then on `main`. The predicate reads `origin/main` in the repository that the caller names, at the time it is asked.

### A commit that the repository does not hold is an error

`merge-base --is-ancestor` exits 128 for a commit the repository does not hold, for example a session from another clone. The predicate raises `GitOperationError` with git's message. It does not answer "not on merged code", because the repository cannot tell.

## Rejected alternatives

- **Reuse the commit of the tool run records.** Rejected: a record exists only for a tool that ran, so a `--no-static-scan` review has none, and its `-dirty` mark covers only that tool's targets (`_read_tree_commit`, `src/devops_cli/security/tool_executor.py`).
- **Reuse `is_git_clean` (`src/devops_cli/git/operations.py`).** Rejected: it catches every exception and answers "dirty", and it runs `git status` without `--no-optional-locks`, so it can write the index of the reviewed checkout.
- **Record "on main" when the review runs.** Rejected: the answer changes when `origin/main` moves, so a stored answer goes stale.
- **Put `ReviewCheckout` in `review/checkout.py`.** Rejected: `ai/review_schema.py` would import the process runner through it. The model sits with `ReviewSessionPayload`, and only the git readers live in `review/checkout.py`.
