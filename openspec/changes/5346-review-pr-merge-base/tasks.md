# Tasks

## 1. Read the merge base and the diff of a compare in the GitHub client

Kind: behavior. Changes: `src/devops_cli/github/client.py`, `tests/github/test_github_client.py`, `tests/fixtures/github/hello_world_pull_request.json`, `tests/roadmap/test_roadmap_draft_readiness.py`.

- [x] 1.1 `tests/github/test_github_client.py::test_the_files_of_a_comparison_come_with_its_merge_base` and `test_the_compare_diff_is_read_as_text` fail: the recorded compare of the base branch and the head commit of octocat/Hello-World pull request 158 gives its files and its merge base, and the client has no merge base in `CompareFiles` and no `get_compare_diff`
  - Verification: `$ uv run devops ci test tests/github/test_github_client.py` fails on the base
- [x] 1.2 Add `merge_base` to `_CompareFiles` and `CompareFiles`, and add `get_compare_diff`, which shares `_read_diff` with `get_pr_diff`. Delete `get_pull_files`, `get_merge_base` and `_Comparison`, and move their tests to the compare read. Replace the recorded pages of the pulls files endpoint with the recorded compare in the fixture
  - Verification: `$ uv run devops ci test tests/github/test_github_client.py tests/roadmap/test_roadmap_draft_readiness.py` passes

## 2. Review a pull request at the merge base of its base branch

Kind: behavior. Changes: `src/devops_cli/ai/review/runner.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/fakes/github.py`, `tests/commands/test_review_scope.py`, `tests/commands/test_review_pr_post.py`, `tests/ai/review/test_review_runner.py`, `tests/ai/review/test_review_path_routing.py`, `tests/ai/client/test_batch_2_review_defects.py`, `tests/git/test_review_worktree_regression.py`.

- [x] 2.1 `tests/commands/test_review_scope.py::test_a_pr_review_reads_the_changes_at_the_merge_base_of_its_base_branch` fails: the payload's `base.sha` is not the merge base, the pulls endpoints still list the stale file `main_only.py`, and the review pages hold that file. `test_a_pr_review_refuses_a_comparison_at_the_file_limit` and `tests/git/test_review_worktree_regression.py::test_run_pr_review_workflow_with_worktree` fail too
  - Verification: `$ uv run devops ci test tests/commands/test_review_scope.py tests/git/test_review_worktree_regression.py` fails on the base
- [x] 2.2 In `_prepare_pr_content`, read the compare of `pull.base.ref` and `pull.head.sha` in the base repository, end the command with `MESSAGES.review.pr_compare_at_file_limit` at the file limit, and read the diff with `get_compare_diff` from the merge base. Give the compare to `_materialize_pr_head` and `_pr_base_revision`, read the conventions and the base text at the merge base, and set `BaseRevision.revision` to it. Give the base worktree that revision, and drop the `pull` parameter of `_run_pr_review_workflow`. List the comment files from the base revision in `resolve_pr_files`. Add `route_compare_diff` and `route_pull_request_changes` to the GitHub fake, and delete `route_merge_base`. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/commands/test_review_scope.py tests/commands/test_review_pr_post.py tests/ai/review/test_review_runner.py tests/ai/review/test_review_path_routing.py tests/ai/client/test_batch_2_review_defects.py tests/git/test_review_worktree_regression.py` passes

## 3. Analyze the files of the compare of the base branch

Kind: behavior. Changes: `src/devops_cli/commands/analyze.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_analyze.py`, `tests/git/test_ai_task_metadata.py`.

- [x] 3.1 `tests/commands/test_analyze.py::test_analyze_pr_reads_the_files_at_the_merge_base_of_its_base_branch` and `test_analyze_pr_warns_that_a_comparison_at_the_file_limit_can_miss_files` fail: the analysis reads the pulls files endpoint, which lists the stale file `main_only.py`
  - Verification: `$ uv run devops ci test tests/commands/test_analyze.py` fails on the base
- [x] 3.2 In `devops ai analyze pr`, read the files with `get_compare_files` of `pull.base.ref` and `pull.head.sha` in the base repository, and warn with `MESSAGES.analyze.pr_compare_at_file_limit` at the file limit. Run `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/commands/test_analyze.py tests/git/test_ai_task_metadata.py` passes

## 4. Documents

Kind: documents. Changes: `docs/SELF_IMPROVEMENT.md`, `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`.

- [x] 4.1 Say in `docs/SELF_IMPROVEMENT.md` that `devops review pr` reads the conventions at the merge base of the head commit and the tip of the base branch, and name the compare reads of `devops_cli.github.client` in the knowledge base
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
