# Tasks

## 1. Measure Baseline Test Duration

- [x] 1.1 Measure baseline test duration for the eight test files <!-- id: 0 -->

## 2. Migrate Test Files to Git Fake

- [x] 2.1 Migrate `tests/commands/test_ci.py` to `git_fake` <!-- id: 1 -->
- [x] 2.2 Migrate `tests/ci/test_fail_to_pass.py` to `git_fake` <!-- id: 2 -->
- [x] 2.3 Migrate `tests/commands/test_test_runner.py` to `git_fake` <!-- id: 3 -->
- [x] 2.4 Migrate `tests/ci/test_ci_cache_fingerprint.py` to `git_fake` <!-- id: 4 -->
- [x] 2.5 Migrate `tests/ci/test_ci_mutate.py` to `git_fake` <!-- id: 5 -->
- [x] 2.6 Migrate `tests/ci/test_ci_cache.py` to `git_fake` <!-- id: 6 -->
- [x] 2.7 Migrate `tests/commands/test_ci_build_index.py` to `git_fake` <!-- id: 7 -->
- [x] 2.8 Migrate `tests/commands/test_uv.py` to `git_fake` <!-- id: 8 -->

## 3. Verify Duration and Quality Gates

- [x] 3.1 Measure test duration after migration and record comparison <!-- id: 9 -->
- [x] 3.2 Pass all quality checks (`uv run devops ci`) <!-- id: 10 -->
