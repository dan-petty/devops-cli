# Tasks

## 1. The guards

- [x] 1.1 Add the failing invariant test: the root parameter of `get_repo_origin_name` has no default. On a0165a16 it reports the default `None` (`uv run devops ci test tests/invariants/test_source_tree.py`).
- [x] 1.2 Add `DEFAULT_CURRENT_PATH` and a parameter default of `Path(".")` to the rule `review-cwd-read`, with rule tests, and show that a restored default in `security/trivy.py` fails the scan (`uv run ast-grep test --skip-snapshot-tests`, `uv run ast-grep scan --filter review-cwd-read`).

## 2. The scanner entry points take their target from the caller

- [x] 2.1 Remove the `.` default from the eleven entry points in `src/devops_cli/security/`, and give `DependencyRemediator` a directory in its tests (`uv run devops ci test tests/test_dependency_remediator.py tests/test_vulnerability_lookup.py`).

## 3. The origin lookup takes its root from the caller

- [x] 3.1 Add the failing tests: the PR review and the check fallback with no repository read the origin in the checkout that they get, and a directory with no repository has no origin when `GITHUB_REPOSITORY` names one (`uv run devops ci test tests/test_review_runner.py tests/test_pr_check_verdict.py tests/test_repos.py`).
- [x] 3.2 Require the root of `get_repo_origin_name` and delete its `GITHUB_REPOSITORY` fallback. Give `find_repo_root(Path.cwd())` in `devops pr`, `devops gh`, `devops roadmap` and `devops review pr`, add `checkout` to `fetch_pr_check_verdicts` and the PR review helper, and require the owner and the repository of `resolve_branch_pr_number` (`uv run devops ci test tests/test_github_pr_monitor.py tests/test_review_worktree_regression.py tests/test_review_scope.py tests/test_pr_cmd.py tests/test_gh_cmd.py tests/test_review.py`).

## 4. Documentation

- [x] 4.1 Describe both guards in ARCHITECTURE.md, section 7.4 (`uv run devops docs check`).
- [x] 4.2 Check the change (`uv run devops openspec check`).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
