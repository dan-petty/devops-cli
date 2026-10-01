# Task: The Workspace Tripwire Fails `devops ci` From Every Linked Worktree (#824)

**Issue**: [#824](https://github.com/dan-petty/devops-cli/issues/824)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/ci

## Description
e8eaf4a (#749) added a workspace tripwire to `tests/conftest.py`. After the test session, it reports each tracked file that tests changed. `_is_git_file_modified` returned True whenever `<root>/.git/index` was missing, without asking git. In a linked worktree, `.git` is a file that points at the main repository, so that path never exists. `uv run devops ci` regenerates the docs and README while pytest runs, so the tripwire reported every regenerated file as modified, and the gate failed from any linked worktree even when every test passed.

## Acceptance Criteria
- [x] `_is_git_file_modified` leaves finding the index to `git diff --quiet`. A git error exits non-zero and still counts as a change.
- [x] `test_check_tracked_diff_compares_content_in_a_linked_worktree` (`tests/test_isolation_tripwire.py`, using the `nested_worktree` fixture) checks that a tracked file whose mtime changed but whose content did not is not reported, and that an edited one is. It fails against e8eaf4a's `conftest.py`.
- [x] `uv run devops ci` passes from a linked worktree.

## Verification
- The new test fails on the original `conftest.py` and passes with the change.
- `uv run devops ci` from this linked worktree: every check passes.
