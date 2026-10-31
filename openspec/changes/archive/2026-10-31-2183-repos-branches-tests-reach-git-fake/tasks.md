# Tasks

## 1. Measure Baseline Test Duration

- [x] 1.1 Measure baseline test duration for the 10 test files <!-- id: 0 -->

## 2. Migrate Test Files to Git Fake

- [x] 2.1 Migrate `tests/commands/test_tf.py` to `process_fake` and pure-Python `nested_worktree` <!-- id: 1 -->
- [x] 2.2 Migrate `tests/core/test_openspec_command.py` and `tests/commands/test_openspec_scaffold.py` <!-- id: 2 -->
- [x] 2.3 Migrate `tests/crypto/test_ssh.py` <!-- id: 3 -->
- [x] 2.4 Migrate `tests/github/test_github_metrics.py` and `tests/github/test_github_pr_monitor.py` <!-- id: 4 -->
- [x] 2.5 Migrate `tests/commands/test_branches.py` <!-- id: 5 -->
- [x] 2.6 Migrate `tests/commands/test_devcontainer.py` <!-- id: 6 -->
- [x] 2.7 Migrate `tests/commands/test_repos.py` <!-- id: 7 -->
- [x] 2.8 Migrate `tests/git/test_repos_worktrees.py` <!-- id: 8 -->

## 3. Verify Duration and Quality Gates

- [x] 3.1 Measure test duration after migration and confirm 0 git subprocess starts <!-- id: 9 -->
- [x] 3.2 Pass all quality checks (`uv run devops ci`) <!-- id: 10 -->
