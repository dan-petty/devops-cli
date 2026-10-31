# Tasks

## 1. Measure Baseline Test Duration

- [x] 1.1 Measure baseline test duration for the 15 review test files <!-- id: 0 -->

## 2. Migrate Test Files to Git Fake

- [x] 2.1 Migrate `tests/ai/review/test_review_backend_activity.py` to `git_fake` <!-- id: 1 -->
- [x] 2.2 Migrate `tests/ai/review/test_review_path.py` to `git_fake` <!-- id: 2 -->
- [x] 2.3 Migrate `tests/ai/review/test_review_runner.py` to `git_fake` <!-- id: 3 -->
- [x] 2.4 Migrate `tests/ai/review/test_review_security_tools.py` to `git_fake` <!-- id: 4 -->
- [x] 2.5 Migrate `tests/commands/test_review_pre_analysis_only.py` to `git_fake` <!-- id: 5 -->
- [x] 2.6 Migrate `tests/ai/review/test_review_repos.py` to `git_fake` <!-- id: 6 -->
- [x] 2.7 Migrate `tests/ai/review/test_runner.py` to `git_fake` <!-- id: 7 -->
- [x] 2.8 Migrate `tests/review/test_review_group_analysis.py` to `git_fake` <!-- id: 8 -->
- [x] 2.9 Migrate `tests/ai/review/test_review_sample_validation.py` to `git_fake` <!-- id: 9 -->
- [x] 2.10 Migrate `tests/ai/review/test_review_samples.py` to `git_fake` <!-- id: 10 -->
- [x] 2.11 Migrate `tests/git/test_review_worktree_regression.py` to `git_fake` <!-- id: 11 -->
- [x] 2.12 Migrate `tests/ai/review/test_review_project_conventions.py` to `git_fake` <!-- id: 12 -->
- [x] 2.13 Migrate `tests/ai/review/test_review_path_routing.py` to `git_fake` <!-- id: 13 -->
- [x] 2.14 Migrate `tests/review/test_review_untrusted_tree.py` to `git_fake` <!-- id: 14 -->
- [x] 2.15 Migrate `tests/security/test_review_tool_runs.py` to `git_fake` <!-- id: 15 -->

## 3. Verify Duration and Quality Gates

- [x] 3.1 Measure test duration after migration and record comparison <!-- id: 16 -->
- [x] 3.2 Pass all quality checks (`uv run devops ci`) <!-- id: 17 -->
