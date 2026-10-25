# Proposal

## Why

Issue #1440: several modules parse git command outputs in human format. Git C-quotes paths with non-ASCII or special characters, formats renames as `old -> new`, and translates strings.

- In `src/devops_cli/argo/gitops.py`, `inspect_git_manifest_drift` strips the output before splitting it. This removes the leading space from a first ` M` status line. The parser then drops the first character of the path. A rename leaves ` -> ` in the path. Non-ASCII paths contain C-escape sequences. The function also resolves paths against the current working directory instead of the repository root.
- In `src/devops_cli/core/repo.py`, `_list_git_tracked_files` runs `git ls-files` without `-z`. C-quoted files such as `"caf\303\251.py"` fail the `is_file()` check and drop out of file lists.
- In `src/devops_cli/commands/test_cmd.py`, `_changed_paths` splits output lines by hand and strips quotes.
- In `src/devops_cli/roadmap/refine.py`, `_collect_repo_map` and `collect_context` read `git ls-tree` without `-z`. C-quoted ADR paths fail later reads.
- In `src/devops_cli/core/cleanup.py`, `_listed_worktrees` reads `git worktree list --porcelain` without `-z`.

## What Changes

- Update `inspect_git_manifest_drift` in `src/devops_cli/argo/gitops.py` to run `git status --porcelain=v1 -z`. Parse entries terminated by null bytes. Handle the original path field for renames. Resolve paths against the repository root.
- Update `_list_git_tracked_files` in `src/devops_cli/core/repo.py` to run `git ls-files -z` and split on null bytes.
- Update `_changed_paths` in `src/devops_cli/commands/test_cmd.py` to run `git diff --name-only -z` and `git status --porcelain=v1 -z`, splitting on null bytes.
- Update `_collect_repo_map` and `collect_context` in `src/devops_cli/roadmap/refine.py` to run `git ls-tree -r -z --name-only` and split on null bytes.
- Update `_listed_worktrees` in `src/devops_cli/core/cleanup.py` to run `git worktree list --porcelain -z` and split on null bytes.
- This change alters no CLI commands, options, messages, manifests, or service behavior. It fixes internal git command parsing.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/argo/gitops.py`: `inspect_git_manifest_drift` and `_parse_drift_event`.
- `src/devops_cli/core/repo.py`: `_list_git_tracked_files`.
- `src/devops_cli/commands/test_cmd.py`: `_changed_paths` and `_porcelain_path`.
- `src/devops_cli/roadmap/refine.py`: `_git`, `_collect_repo_map`, and `collect_context`.
- `src/devops_cli/core/cleanup.py`: `_listed_worktrees`.
- `tests/test_argo_gitops.py`: unit tests for drift parsing with real git repository.
- `tests/test_repos.py`: unit tests for `list_repo_files` with non-ASCII and spaced paths.
- `tests/test_test_cmd.py`: unit tests for `_changed_paths` with non-ASCII, spaces, and renames.
- `tests/roadmap/test_refine.py`: unit tests for `collect_context` with non-ASCII and spaced ADR paths.
- `tests/core/test_cleanup_fuzzing.py`: update worktree list test to use null-separated output.

## Feasibility

- Git version 2.55.0 on Linux confirms the null-separated formats:
  - `git status --porcelain=v1 -z` separates entries with null bytes. Renames supply the new path followed by the old path as a separate field. Paths with spaces or non-ASCII characters remain unquoted. Unstaged modifications retain the leading space (for example, ` M`).
  - `git ls-files -z` provides raw unquoted paths separated by null bytes.
  - `git diff --name-only -z` provides raw unquoted paths separated by null bytes.
  - `git ls-tree -r -z --name-only` provides raw unquoted paths separated by null bytes.
  - `git worktree list --porcelain -z` separates all records and attributes with null bytes.
- Python tests in temporary git repositories reproduced each defect:
  - `argo/gitops.py`: `k8s/app.yaml` with status ` M` lost the leading character when the output was stripped.
  - `core/repo.py`: `café.py` was listed with C-escapes (`"caf\303\251.py"`) and omitted from results.
  - `commands/test_cmd.py`: quoted paths with spaces or non-ASCII characters were corrupted.
  - `roadmap/refine.py`: `docs/adr/0001-café.md` was quoted and could not be read.
  - `core/cleanup.py`: worktrees with spaces or non-ASCII characters were split on newlines.

## Existing Tool Considered

Git CLI with the `-z` option and Python standard library string methods (`str.split("\0")`) cover the need. The codebase already uses `-z` in `git/operations.py`, `git/worktree_inventory.py`, and `core/cleanup.py`. No new library or custom string parser is necessary.
