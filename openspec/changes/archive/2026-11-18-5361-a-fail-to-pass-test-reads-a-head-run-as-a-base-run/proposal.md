# Proposal: #5361

## Why

In `tests/ci/test_fail_to_pass.py`, the helper `_ran_on_base` reads a gate row call as a base run
when the name of its working folder is `tree`. The base replay tree of the fake is always
`<temp-dir>/tree`, so the folder name stood in for it. The test
`test_the_command_exits_0_for_a_gate_check_that_proves_the_fix` runs `devops ci fail-to-pass` with
no root, so the command takes the worktree of the current folder as the root, and the head run of
the gate row runs in that root. When that checkout's folder is named `tree`, the fake answers the
head run with the base output: the case then fails on head too, the replay proves nothing, and the
test fails on base. Closes #5361.

## What Changes

- The fake records the base worktree that `git worktree add` made, and `_ran_on_base` identifies a
  base run by that recorded path (or a folder inside it), not by the working folder name.
- A folder named `tree` that no `git worktree add` recorded is a head run.

## Capabilities

None: this changes a test fake, not product behavior. `skip_specs` is set.

## Impact

- The replay test passes in a checkout of any folder name, and the fake answers each gate row from
  the worktree the run recorded.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: the fake already records each `git worktree add` destination in
  `active_worktrees` (`tests/ci/test_fail_to_pass.py:168`), and the base replay tree is always
  `tmp / "tree"` (`src/devops_cli/ci/fail_to_pass.py:910`). The base worktree is the recorded one
  named `tree`; a head worktree (`<temp-dir>/head`) and a plain-base worktree
  (`<temp-dir>/plain_base`) are not it.

## Existing Tool Considered

The alternatives check of 2026-11-17 recorded verdict none and no tool. No open, maintained tool or
library covers the need: the change edits the existing test fake and adds no library.
