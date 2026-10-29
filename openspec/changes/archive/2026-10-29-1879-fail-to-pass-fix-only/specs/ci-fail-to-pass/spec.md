## Purpose

When the fail-to-pass check runs on a pull request, what the replay reads, and what its report tells the author: only a fix that changes the code under `src/` must show a changed test that fails on its base.

## ADDED Requirements

### Requirement: The check runs only for a fix that changes the code under src
The fail-to-pass workflow SHALL start only for a pull request into `main` that changes a path under `src/` outside `src/devops_cli/ai/knowledge_base/`, and its job SHALL run only for a title that `CONST_DEFECT_TITLE_PATTERN` reads as a fix.

#### Scenario: A pull request that is not a fix
- **WHEN** the job condition of `.github/workflows/fail-to-pass.yml` is evaluated for the titles `feat(ci): add a check`, `docs(ci): describe the check`, `chore(main): release 1.0.0` and `fixup: squash a commit`
- **THEN** the job does not run for any of them

#### Scenario: A fix title
- **WHEN** the job condition is evaluated for `fix(ci): replay the changed tests`, `fix: replay the changed tests` and `FIX(ci): replay the changed tests`
- **THEN** the job runs for each of them

#### Scenario: A change outside the code under src
- **WHEN** the path filter of the workflow is evaluated for `tests/test_fail_to_pass.py`, `Dockerfile`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/testing.md` and the files of a release pull request
- **THEN** the workflow does not start for any of them, and it starts for `src/devops_cli/ci/fail_to_pass.py`

### Requirement: The replay reads no title, label or body
`devops ci fail-to-pass` SHALL take no pull request title, label or body, and SHALL fail unless at least one changed test fails in the call phase on base.

#### Scenario: An escape line in the environment
- **WHEN** `PR_TITLE` is `feat(ci): add a check`, `PR_BODY` holds `Fail-to-pass: not applicable: the tests pass on base`, and every changed test passes on base
- **THEN** `devops ci fail-to-pass --base main` exits 1 and prints no `not applicable` line

#### Scenario: The removed options
- **WHEN** `devops ci fail-to-pass` gets `--title`, `--labels` or `--body`
- **THEN** it exits 2 as for an unknown option

### Requirement: A replay that cannot run names the next step
When the replay's pytest is interrupted, stops with an internal or usage error, or writes no complete JUnit report, the check SHALL fail, and its report SHALL tell the author to merge the change to the test harness or the dependencies first, in a pull request that is not a fix.

#### Scenario: pytest stops with an internal error
- **WHEN** the replay's pytest exits with status 3 and writes no JUnit report
- **THEN** the command exits 1, and its report says that the replay could not run and to merge the change to the test harness or to the dependencies first, in a pull request that is not a fix
