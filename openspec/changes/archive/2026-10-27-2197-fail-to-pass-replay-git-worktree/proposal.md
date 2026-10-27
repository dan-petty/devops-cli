# Proposal

## Why

Issue #2197: `devops ci fail-to-pass` replays the changed tests in a directory that `git archive` filled. That directory is not a git work tree. A test that runs `git ls-files` there exits with status 128. The replay then reports the test as failed on base for a reason of its own, and a reader takes it for a fail-to-pass result.

## What Changes

- The replay checks out the merge base as a detached git worktree of the checkout (`git worktree add --detach`), overlays the head's `tests/`, runs pytest, and always removes the worktree.
- A failure to add the worktree raises a `GitOperationError` with the git message.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option or output format changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/test_fail_to_pass.py`.

## Feasibility

- Issue #2197 records git exit 128 in the replay directory on the #1817 branch.
- Command output: `uv run pytest` on the new test fails on the unchanged code with 1 failed test on base, and passes with the worktree.

## Existing Tool Considered

Built-in `git worktree`. It replaces the `git archive` extraction of the base tree. The change deletes that extraction of the base tree.
