# Proposal

## Why

The Fail-to-Pass Check refuses a change that repairs a red `main` (#5590).
While `main` is red, an unchanged test fails on the merge base of every change.
The check refuses each change for it, so no change can repair `main`.
An agent cannot mark such a pull request ready.
The check refuses for an unchanged test even when the change makes that test pass on the head.
A repair of `main` is not an unclean replay.
The check must accept an unchanged test that was red on `main` and that the head repairs.
To keep the protection of #3124, the check must prove that the test failed on the plain merge base.
The check must still refuse an unchanged test that passes on the plain merge base or that fails on the head.

## What Changes

- The check replays unchanged failures on the plain merge base with no head tests overlaid.
- The check also replays those test files on the head tree.
- The head tree is the working tree for `HEAD`, or one detached worktree for a named head.
- An unchanged test is repaired only when it fails on the plain merge base and passes on the head.
- An unchanged test that passes on the plain merge base was broken by changed test files, so it still refuses the replay (#3124).
- An unchanged test that does not pass on the head still refuses the replay.
- The gate counts only a changed test that fails on base, so a repaired test alone satisfies nothing.
- A head replay that writes no complete JUnit report refuses the replay and names pytest's exit status.
- `devops ci fail-to-pass --dry-run` lists the head replay with its condition.
- The report names each repaired test in a dedicated line.
- `CONTRIBUTING.md:179` updates the fail-to-pass evidence documentation to describe repaired tests and plain merge-base verification.
- `src/devops_cli/lang/en/help.py` updates the `--head` help message, and `devops docs generate` updates generated documentation.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-fail-to-pass`: Replay unchanged failures on the plain merge base and on the head tree to accept repairs of a red `main` while keeping #3124 protection.

## Impact

- Code: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Docs: `CONTRIBUTING.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`
- Tests: `tests/ci/test_fail_to_pass.py`

## Feasibility

- The check reads no GitHub state today.
- `run_fail_to_pass` starts git and pytest.
- Replaying unchanged failures on the plain merge base requires a detached worktree of the merge base with no head tests overlaid.
- Replaying unchanged failures on the head tree uses the working tree for `HEAD` and a detached worktree for a named head.
- The head replay shares the detached worktree with the head gate rows when both run.
- When no unchanged failure occurs, neither secondary replay runs.
- `_unsatisfied_reasons` puts the head could-not-run branch after the host path guard branch.
- The check skips secondary replays when a guard failure already refuses the replay.
- The test harness supports multiple pytest runs in separate directories.
- `CONTRIBUTING.md:179` needs updates for the new repaired test rule and the plain merge-base check.
- `src/devops_cli/lang/en/help.py:970` needs an updated `--head` description, synchronized by `devops docs generate`.
- The first check is `uv run devops ci test tests/ci/test_fail_to_pass.py`.
- The change fits standard runner resources and timeouts.

## Existing Tool Considered

git worktree and pytest are open and maintained, and give the head tree and the JUnit outcomes; neither classifies an unchanged failure as a repair, so the change adds that classification to the in-repo check. Written cost: about 100k tokens to build, keep and fix the classification and its tests, over about 4 hours.

## Dependencies

None.
