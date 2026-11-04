# Proposal

## Why

The base replay of `devops ci fail-to-pass` runs in a linked git worktree under the temporary directory (#3124). The telemetry tracer reads the `HEAD` file of the git directory of that worktree. That file lies under the common git directory of the checkout, and the host path guard of the test harness refuses it. Each test of the replay then fails with `host path reached without a fake`, and the check passes for a fix whose changed tests pass on the base. The same guard stops test runs in a runner worktree.

## What Changes

- The host path guard allows the common git directory of a linked worktree. `tests/support/host_paths.py` holds the allowed roots and reads that directory with `_linked_worktree_common_dir` of `src/devops_cli/core/repo.py`, so no `git` process starts. The root conftest calls the module.
- The root conftest no longer lists the main worktree path `/workspaces/devops-cli`. The new root covers a worktree of that checkout, and the replay shows that the guard accepts the replay tree without the path.
- `satisfied` in `src/devops_cli/ci/fail_to_pass.py` is false when a failure or an error carries `reached without a fake`, the phrase of every harness guard (host path, network edge, process edge and keyring edge).
- `satisfied` is false when a test that the fix does not change fails on the base. `src/devops_cli/ci/changed_tests.py` compares the syntax tree of each failed test function in the replay tree (the head) with the function at the merge base. A new test, or a test that a source does not show, counts as changed, so a fix with one new test that fails in full stays satisfied.
- The report names the guard failure or the unchanged tests. The dry run lists the two git reads of the comparison.
- `CONTRIBUTING.md` and `docs/TESTING.md` describe the new rules. No command, option or flag changes, so the help text and the generated documents stay the same.

## Capabilities

### New Capabilities

- `test-host-path-guard`: The roots that the host path guard of the test harness allows

### Modified Capabilities

- `ci-fail-to-pass`: A replay with a guard failure or an unchanged failed test proves nothing

## Impact

- Code: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/ci/changed_tests.py`, `src/devops_cli/git/operations.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/conftest.py`, `tests/support/host_paths.py`, `tests/invariants/test_host_path_roots.py`, `tests/ci/test_fail_to_pass.py`, `tests/ci/test_changed_tests.py`
- Documents: `CONTRIBUTING.md`, `docs/TESTING.md`

## Feasibility

- The reproduction confirms the cause. A throwaway test that calls `_detect_vcs_metadata` failed in the replay with `host path reached without a fake: /workspaces/devops-cli/.git/worktrees/tree10/HEAD` and a teardown error `network edge reached without a fake`, when the roots hold the checkout and not the common git directory. `uv run devops ci fail-to-pass --base origin/main` printed it in this worktree, where the replay tree is under `/tmp` and the common git directory is under another root, the same layout as the runner. With the new root, the same run passed that test.
- The code that reads the file is `_read_git_head_ref` in `src/devops_cli/telemetry/tracer.py`: `_detect_vcs_metadata` calls `_resolve_git_dir`, which returns `<common dir>/worktrees/<name>` for a worktree, and `_read_git_head_ref` opens `HEAD` there.
- `_linked_worktree_common_dir` in `src/devops_cli/core/repo.py` returns the common git directory from the `.git` file and the `commondir` file with file reads only. A submodule and a plain checkout give none.
- With the main worktree path removed, `uv run devops ci fail-to-pass --base origin/main` replayed a changed `tests/ai/mcp/test_mcp.py` (172 tests) in the replay tree and all tests passed with no guard message. This is the runner form of #3230: a worktree whose common git directory lies outside the checked-out tree. The devcontainer form, a worktree inside `/workspaces/devops-cli`, runs the whole test suite under the same roots. Two tests fail there on this change and on `origin/main` alike, because the container holds a tool that they expect to be absent.
- The JUnit message of a guard failure holds the guard phrase on its first line, for a call failure and for a teardown error. The issue log shows both.
- No `git rev-parse` runs in the conftest, and the floor refuses any process start, so a test with `process_fake` shows that the roots start none.

## Existing Tool Considered

No open, maintained tool or library covers this need. The change edits the hermetic guard and the fail-to-pass gate of this repository. For the comparison of tests, the standard `ast` module gives the syntax tree and `ast.dump` the comparison, and the existing `read_file_at_revision` reads the merge-base text. The cost is about 30,000 tokens to build, about 5,000 tokens to keep and fix, and about 3 hours.

## Dependencies

None.
