# Proposal: #5346

## Why

The issue #5346 reports that `devops review pr` and `devops ai analyze pr` read a stale change set. The review read the files of a pull request from the pulls files endpoint and its diff from the pulls endpoint, and it read the base text at the merge base of the payload's `base.sha` and the head commit. It also gave `base.sha` to the review worktrees as the base revision. GitHub does not move `base.sha` when a merge commit moves the merge base of a pull request, and the pulls files and diff endpoints keep that stale base too. Thus, after a person merges `main` into a pull request branch, the review reads the changes of `main` as changes of the pull request. `devops ai analyze pr` read the pulls files endpoint and has the same defect. The issue #2530 fixed the same cause in `devops pr check-readiness`.

## What Changes

- `devops review pr` reads the files of a pull request from the compare of the tip of its base branch and its head commit (`compare/<base-ref>...<head-sha>`), in the base repository. This is the diff that the squash merge applies.
- The review reads the diff from the compare of that merge base and the head commit (`compare/<merge-base>...<head-sha>`, diff media type), so the files and the diff come from one merge base.
- The review reads the base text of each changed file and the base conventions at that merge base. No request of the review names the payload's `base.sha`.
- The base worktree of the review is at that merge base. The fetch of the pull request head brings the merge base to the local repository.
- A compare at GitHub's limit of 300 files ends `devops review pr` with status 1 and a message that names the limit and `devops review branch`. The compare diff has no such limit, but the review needs every changed file for the head files, the symbol deltas and the filter of deleted files.
- When the diff names no reviewable file, the comment of `devops review pr --post` lists the files of the compare that the review read. The command does not read the file list a second time.
- `devops ai analyze pr` reads the files of a pull request from the compare of the tip of its base branch and its head commit. A compare at the limit gives an analysis of the listed files and a warning that names the limit.
- `GitHubClient.get_compare_files` also returns the merge base of the compare, and the new `GitHubClient.get_compare_diff` reads the diff of two commits. `GitHubClient.get_pull_files` and `GitHubClient.get_merge_base` have no caller after this change, so the change deletes them.
- The change alters the output of two commands, so it carries a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

- `pr-squash-diff`: A PR review reads the diff that the squash merge applies, A PR review refuses a compare at the file limit, The PR analysis reads the files of the compare of its base branch

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/github/client.py`, `src/devops_cli/ai/review/runner.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/commands/analyze.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/analyze/symbols.py` (the docstring of `BaseRevision.revision`), `src/devops_cli/config/constants.py` (the comment of `CONST_GITHUB_DIFF_MEDIA_TYPE`)
- Docs: `docs/SELF_IMPROVEMENT.md`, `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`
- Tests: `tests/github/test_github_client.py`, `tests/commands/test_review_scope.py`, `tests/commands/test_review_pr_post.py`, `tests/commands/test_analyze.py`, `tests/ai/review/test_review_runner.py`, `tests/ai/review/test_review_path_routing.py`, `tests/ai/client/test_batch_2_review_defects.py`, `tests/git/test_review_worktree_regression.py`, `tests/git/test_ai_task_metadata.py`, `tests/roadmap/test_roadmap_draft_readiness.py`, `tests/support/fakes/github.py`, `tests/fixtures/github/hello_world_pull_request.json`

## Feasibility

- A live probe on 2026-11-13 confirmed the premise. `devops gh api repos/dan-petty/devops-cli/pulls/2509` gave state closed, merged true, `base.sha` 0137f231, `base.ref` main, head 344adba9 and 184 changed files.
- `compare/0137f231...344adba9?per_page=1` gave merge base 0137f231 and 184 files, and `compare/main...344adba9?per_page=1` gave merge base 5c4d24ee and 11 files, the files of the squash commit.
- The diff of the pulls endpoint (`pulls/2509` with `Accept: application/vnd.github.diff`) held 184 `diff --git` headers, and the diff of `compare/main...344adba9` held 11. So the diff that the review read was stale too, not only its file list.
- `compare/v0.100.0...v0.127.0?per_page=1` listed 300 files, the limit, and its diff media type held 3394 `diff --git` headers. So the compare diff has no 300-file limit, and the file list is the read that can be partial.
- `compare/master...ec18ca7b` of octocat/Hello-World pull request 158 gave merge base 7fd1a60b and its 2 files. The change records that answer in `tests/fixtures/github/hello_world_pull_request.json`.
- The source of `origin/main` showed the stale reads: `src/devops_cli/ai/review/runner.py:952` read `get_pr_diff`, line 957 read `get_pull_files`, line 988 read `get_merge_base(base_repo, pull.base.sha, pull.head.sha)`, line 1015 read the conventions at `pull.base.sha`, and line 278 read `get_pull_files` for the comment. `src/devops_cli/commands/review.py:731` gave `pull.base.sha` to the worktrees, and `src/devops_cli/commands/analyze.py:537` read `get_pull_files`.
- `git grep` for `get_pull_files` and `get_merge_base` in `src/` showed no caller other than these reads.

## Existing Tool Considered

- The GitHub REST compare endpoint covers the need: it compares from the merge base of the base branch and the head, and it serves the diff in the diff media type. The change uses `GitHubClient.get_compare_files`, which #2530 added for readiness, and adds no second copy of that read.
- The change deletes `GitHubClient.get_pull_files`, `GitHubClient.get_merge_base`, the model `_Comparison`, the test route `route_merge_base`, the `pull` parameter of `_run_pr_review_workflow`, and the second file read of the PR comment.
