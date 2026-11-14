# Design

## Decisions

- **Replay unchanged failures on the plain merge base and on the head tree.**:
  The check proves that an unchanged failure was red on `main` without head test pollution (#3124).
  It runs pytest on the plain merge base with no head tests overlaid.
  It also runs pytest on the head tree.
  A test counts as repaired only when it fails on the plain merge base and passes on the head.
  An unchanged test that passes on the plain merge base was broken by changed test files, so it still refuses the replay.
- **Run the head replay and the head gate rows in `_head_tree`.**:
  One context manager manages the head tree.
  `HEAD` uses the working tree, and a named head uses a detached worktree.
  This avoids duplicate worktrees and keeps uncommitted changes.
- **Run the plain merge base replay in `_plain_base_tree`.**:
  A detached worktree checked out at the merge base without head tests overlaid.
  The worktree is added and removed only when an unchanged test fails.
- **Skip secondary replays when guard failures or could-not-run occur.**:
  If the base replay hits a host path guard failure or could not run, the check stops.
  It skips the plain base replay and the head replay because the replay is already refused.
- **Count only a changed test as a base failure that satisfies the gate.**:
  The base requirement says the command SHALL fail unless at least one changed test fails on base.
  A repaired unchanged test removes its refusal, but alone does not satisfy the gate.
- **Name each repaired test in the report.**:
  The author sees why an unchanged failure no longer refuses the replay.
- **Update documentation and help text.**:
  Update `CONTRIBUTING.md:179` to document the repaired test rule and plain merge-base check.
  Update `src/devops_cli/lang/en/help.py:970` (`fail_to_pass_head`) and synchronize generated documents.

## Rejected alternatives

- **Read the Tests & Coverage run of main at the base commit.**:
  Rejected. It requires network access, GitHub API authentication, and run artifact mapping.
  The check currently requires only local git and pytest.
- **Replay only on the head without checking the plain merge base.**:
  Rejected. It removes the #3124 protection against unclean replays.
  Changes to shared test fixtures could break an unchanged test on base while passing on head.
- **Always add a detached worktree for the head replay.**:
  Rejected. It misses uncommitted changes in the working tree and copies the checkout unnecessarily.
- **Let a repaired unchanged test satisfy the gate alone.**:
  Rejected. A repair alone does not prove that the fix adds or changes a test for its changes.
