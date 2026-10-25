# Tasks

## 1. Drift Events and Repository Files

- [x] 1.1 Write failing tests in `tests/test_argo_gitops.py` and `tests/test_repos.py` for `inspect_git_manifest_drift` and `list_repo_files` in a real git repository with ` M` status, paths with spaces, non-ASCII paths, and renames. Verify with `uv run devops ci test tests/test_argo_gitops.py tests/test_repos.py`.
- [x] 1.2 Update `inspect_git_manifest_drift` in `src/devops_cli/argo/gitops.py` to use `git status --porcelain=v1 -z`, consume rename fields, and resolve paths relative to the repository root. Verify with `uv run devops ci test tests/test_argo_gitops.py tests/argo/test_gitops_fuzzing.py`.
- [x] 1.3 Update `_list_git_tracked_files` in `src/devops_cli/core/repo.py` to use `git ls-files -z` and split on null bytes. Verify with `uv run devops ci test tests/test_repos.py`.
- [x] 1.4 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 2. Test Selection, Refinement Context, and Worktree List

- [x] 2.1 Write failing tests in `tests/test_test_cmd.py` and `tests/roadmap/test_refine.py` for test selection and refinement context with paths containing spaces, non-ASCII characters, and renames. Verify with `uv run devops ci test tests/test_test_cmd.py tests/roadmap/test_refine.py`.
- [x] 2.2 Update `_changed_paths` and `_porcelain_path` in `src/devops_cli/commands/test_cmd.py` to run `git diff --name-only -z` and `git status --porcelain=v1 -z`. Verify with `uv run devops ci test tests/test_test_cmd.py`.
- [x] 2.3 Update `_git`, `_collect_repo_map`, and `collect_context` in `src/devops_cli/roadmap/refine.py` to run `git ls-tree -r -z --name-only`. Verify with `uv run devops ci test tests/roadmap/test_refine.py`.
- [x] 2.4 Update `_listed_worktrees` in `src/devops_cli/core/cleanup.py` to run `git worktree list --porcelain -z` and update `tests/core/test_cleanup_fuzzing.py` for null-separated output. Verify with `uv run devops ci test tests/core/test_cleanup_fuzzing.py`.
- [x] 2.5 Regenerate documentation with `uv run devops docs generate --sync-readme`.


## 3. Verification

- [x] 3.1 Run full CI checks. Verify with `uv run devops ci`.


## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
