# Tasks

## 1. Measure the suite

- [x] 1.1 Run the suite with `--durations=0` and, in a second run, with `COVERAGE_CORE=ctrace --cov-context=test --cov-branch`; join the seconds and the lines of each test; write the result and the method in design.md. Verified by: the commands in the Measurement section of design.md.

## 2. Gate the changed lines

- [x] 2.1 Change `test_changed_line_coverage_step_fails_a_pull_request_below_ninety_percent` in `tests/test_ci.py` to expect `--fail-under 90` and the exit with the status of `diff-cover` after the pragma list, and watch it fail. Verified by: `uv run devops ci test tests/test_ci.py`.
- [x] 2.2 Add `--fail-under 90` to the `Changed-Line Coverage` step of `.github/workflows/ci.yml`; keep the status of `diff-cover`, append the pragma list, and exit with the status. Verified by: `uv run devops ci test tests/test_ci.py`, and a run of the step's `run` block in a scratch repository for a change with no source line, a fully covered change and a half covered change.

## 3. Lower the floor

- [x] 3.1 Add `test_the_contributor_guide_and_the_test_rules_state_the_coverage_floor_of_pyproject` and its negative control to `tests/test_agents_md_claims.py`. Verified by: `uv run devops ci test tests/test_agents_md_claims.py`.
- [x] 3.2 Set `fail_under = 85` in `pyproject.toml`; state the floor and the changed-line gate in `CONTRIBUTING.md` and `docs/TESTING.md`; name the gate without a figure in `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, the feature request form and three knowledge base documents. Verified by: `uv run devops ci test tests/test_agents_md_claims.py` and `uv run devops ci --only test`.

## 4. Decide on the removal of tests

- [x] 4.1 Write in design.md why the change removes no test, with the numbers of the measurement. Verified by: reading the Decisions section of design.md.

## 5. File the follow-up work

- [x] 5.1 File the sub-issues for the causes that the measurement shows, with their numbers, and link them to #2356 as sub-issues. Verified by: `uv run devops gh api repos/dan-petty/devops-cli/issues/2356/sub_issues`.

## Workflow follow-up

- Sub-issues of #2356 for the causes that the measurement shows, each with its own change and pull request: #2369 (the startup-import tests start 56 interpreters), #2371 (what each of the 16 workers repeats at start) and #2373 (what coverage and branch measurement cost).
- Not filed, because nothing has measured them yet: shards of the suite by recorded duration (`pytest-split`) with combined coverage, the slowest Hypothesis tests and the `ci` profile, and the count of tests that start a real process (git, `uv`). They stay on #2356.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
