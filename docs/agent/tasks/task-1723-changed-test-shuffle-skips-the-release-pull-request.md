# Task: The Changed-Test Shuffle Runs Only on Pull Requests into a Release Branch (#1723)

**Issue**: [#1723](https://github.com/dan-petty/devops-cli/issues/1723)
**Scope**: scope/ci
**Feasibility**: `.github/workflows/ci.yml`'s `changed-tests` job (Changed-Test Independence) ran on `if: github.event_name == 'pull_request'`, so the v0.2.37 release pull request (#1720, `release/v0.2.37` into `main`) ran it over every test file the release touched: run 39430481325, job 118653930463, spent more than 20 minutes in "Run Changed Tests in Shuffled Order". Item pull requests target the release branch; the only pull requests into `main` are release pull requests, whose items each passed the job against the release branch.

## Description

- The job's condition is `github.event_name == 'pull_request' && github.base_ref != 'main'`, so it does not run on the release pull request into main. Nothing else changes; item pull requests into `release/**` keep it. #1721 made the same change for the fail-to-pass check.

## Acceptance Criteria

- [x] Tests first: `tests/test_ci_repeat.py::test_the_changed_test_job_reruns_added_or_modified_test_files` pins the job's condition; it failed on the base, whose condition had no `base_ref` term.
- [x] `uv run devops ci` passes (pre-push hook).
- Pending a person: #1720's next head shows Changed-Test Independence as skipped.

## Deliverables

- [x] `.github/workflows/ci.yml` and `tests/test_ci_repeat.py`.
- [x] `changelog.d/1723.md` and this task file.
