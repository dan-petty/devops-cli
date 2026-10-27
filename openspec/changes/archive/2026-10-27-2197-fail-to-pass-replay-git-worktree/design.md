# Design

The replay adds the worktree in a temporary directory, so the checkout keeps its files. A `finally` block runs `git worktree remove --force` and `git worktree prune`, so an error in pytest leaves no worktree.

## Rejected alternatives

- **`git init` in the extracted tree**: The tree then has one commit and none of the history that a test can read. A test that reads history still fails for the replay's own reason.
- **Report the git failure as a replay failure**: The replay then cannot run such a test at all, and the change would stay unverified.

## Test

`tests/test_fail_to_pass.py` has a test with a real git repository: a changed test runs `git ls-files` and passes on base. A second test checks that the checkout lists no extra worktree after the replay.
