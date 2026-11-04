# ci-fail-to-pass Specification

## Purpose
When the fail-to-pass check runs on a pull request, what the replay reads, and what its report tells the author: only a fix that changes the code under `src/` must show a changed test that fails on its base.

## Requirements

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

### Requirement: A host path guard failure refuses the replay
`devops ci fail-to-pass` SHALL treat a replay as not satisfied when a failure or an error of the replay carries the message `host path reached without a fake`, which the host path guard of the test harness writes, and its report SHALL name the tests that carry it and the two causes: a path that the harness does not allow, and a path that a test reads with no fake.

#### Scenario: A host path guard failure
- **WHEN** a changed test fails on base and another test of the replay fails with `Failed: host path reached without a fake: <checkout>/.git/worktrees/tree/HEAD`
- **THEN** the command exits 1, and its report says that the host path guard of the test harness stopped the replay, names the second test and names the two causes

#### Scenario: A host path guard error on teardown
- **WHEN** a test of the replay errors on teardown with `Failed: host path reached without a fake`
- **THEN** the command exits 1 and the report names that guard failure

### Requirement: A network, process or keyring edge failure keeps the replay valid
`devops ci fail-to-pass` SHALL NOT treat the message of the network, process or keyring guard of the test harness as a reason to refuse a replay, since a fix that stops code from reaching an edge proves itself by a changed test that fails on base at that edge.

#### Scenario: A changed test fails at a process edge
- **WHEN** a changed test fails on base with `Failed: process edge reached without a fake: gh api user`
- **THEN** the replay is satisfied

### Requirement: A failed test that the fix does not change refuses the replay
`devops ci fail-to-pass` SHALL treat a replay as not satisfied when a test fails on base in a changed test file though the function of that test and the rest of its file have the same syntax tree in the replay tree and at the merge base, and its report SHALL name that test.

#### Scenario: An unchanged test fails
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that also fails on base
- **THEN** the command exits 1, and its report says that a test the fix does not change fails on base and names the unchanged test

#### Scenario: A comment changes no test
- **WHEN** the head of a test only adds a comment or a blank line to a test that fails on base
- **THEN** the test counts as unchanged

#### Scenario: A changed helper changes every test
- **WHEN** the head of a changed test file changes a helper of that file, and a test that calls the helper and that the fix leaves alone fails on base
- **THEN** the replay is satisfied

### Requirement: One new test that fails on base keeps the replay valid
`devops ci fail-to-pass` SHALL treat a test that the fix adds as changed, so a fix with one new test that fails on base is satisfied when no failure carries the message of the host path guard.

#### Scenario: The only test of the file is new
- **WHEN** a fix adds one test to a test file and the replay fails that test with an assertion
- **THEN** the replay is satisfied
