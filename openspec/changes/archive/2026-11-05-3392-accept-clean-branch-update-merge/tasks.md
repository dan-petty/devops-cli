# Tasks

## 1. The clean merge for the implement job and the stage reconcile

Kind: behavior. Reads: `src/devops_cli/roadmap/clone_git.py`, `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/stage.py`. Changes: `tests/support/roadmap_stage.py`, `tests/roadmap/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_stage_reconcile.py`, `src/devops_cli/git/branch_authors.py`, `src/devops_cli/roadmap/clone_git.py`.

- [x] 1.1 Add `push_merge` and `push_conflict_merge` to `StageRepo` in `tests/support/roadmap_stage.py`. Write the failing tests in `tests/roadmap/test_roadmap_implement_selection.py`: a clean merge of the default branch by a person leaves the branch taken; a person merge that changes a file leaves the branch out and names the author; a person merge that resolves a conflict leaves the branch out and names the author. Write the failing test in `tests/roadmap/test_roadmap_stage_reconcile.py`: a closed item whose branch holds only a clean merge by a person loses the branch. The first and the last test fail on the base for the reason that the branch holds a commit by a person. The file-changing and conflict tests pass on the base, and they guard the refusal.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_stage_reconcile.py` fails on the clean-merge tests, and names the author in the reason.
- [x] 1.2 Add `src/devops_cli/git/branch_authors.py` with the log format and `person_authors`, which leaves out a clean merge. Make `branch_authors` in `src/devops_cli/roadmap/clone_git.py` read the log with that format and call `person_authors`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_stage_reconcile.py` passes.

## 2. The clean merge for the takeover of worktrees add

Kind: behavior. Reads: `src/devops_cli/git/branch_authors.py`, `src/devops_cli/git/worktree_add.py`. Changes: `tests/core/test_repos_worktrees_add.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/roadmap/request_plan.py`.

- [x] 2.1 Write the failing tests in `tests/core/test_repos_worktrees_add.py`: a clean merge by a person is taken over, with the commit count of the App only; a merge by a person that changes a file is refused and names the author; a merge by a person that resolves a conflict is refused and names the author. Update the dry-run test to the new log format. The clean-merge test and the dry-run test fail on the base.
  - Verification: `uv run devops ci test tests/core/test_repos_worktrees_add.py` fails on the clean-merge test and on the dry-run test.
- [x] 2.2 Make `_commands` and the takeover in `src/devops_cli/git/worktree_add.py` read the log with the format of `branch_authors.py` and call `person_authors`. Make the implement dry-run plan in `src/devops_cli/roadmap/request_plan.py` list the same format.
  - Verification: `uv run devops ci test tests/core/test_repos_worktrees_add.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_implement_selection.py` passes.

## 3. Documents

Kind: documents. Changes: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/roadmap/stage.py`, `CONTRIBUTING.md`.

- [x] 3.1 Change the docstring of the implement job (line 28) and the docstrings of `worktree_add.py` (the module and the takeover functions) so that they say a clean merge by a person is not an author.
  - Verification: `uv run devops ci --check --only lint,format`
- [x] 3.2 Change the docstrings of `_foreign_commits` and `_reconcile` in `src/devops_cli/roadmap/stage.py` so that they say a clean merge by a person is not a commit of another author.
  - Verification: `uv run devops ci --check --only lint,format`
- [x] 3.3 Change the paragraph on starting work in `CONTRIBUTING.md` so that it says a clean merge by a person does not hold a branch, and that a merge which changes a file or resolves a conflict still holds it. Run `uv run devops docs generate --sync-readme`.
  - Verification: `uv run devops ci docs`

## 4. Archive

Kind: documents.

- [x] 4.1 Archive the change with `uv run devops openspec archive 3392-accept-clean-branch-update-merge`.
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
