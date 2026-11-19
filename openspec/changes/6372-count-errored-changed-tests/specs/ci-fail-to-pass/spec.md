## ADDED Requirements

### Requirement: A changed test that errors on base proves the fix
`devops ci fail-to-pass` SHALL count a changed test that errors on base at collection or setup as a proof of the fix, as it counts a changed test that fails in the call phase. An error at teardown SHALL NOT prove the fix. A collection error names a whole test file: it SHALL count as changed when the syntax tree of the file differs from the merge base or the file is new. The report SHALL name each changed test that proves the fix.

#### Scenario: The only changed test file fails to collect on base
- **WHEN** the fix changes `tests/test_sample.py`, and the replay reports only a collection error of `tests.test_sample`
- **THEN** the command exits 0, and its report names `tests.test_sample` as errored on base and as the proof of the fix

#### Scenario: A changed test errors on setup
- **WHEN** a changed test errors on base with `failed on setup with "AttributeError: module has no attribute 'new_field'"`
- **THEN** the replay is satisfied

#### Scenario: A changed test errors only at teardown
- **WHEN** the only changed test passes in the call phase on base and errors with `failed on teardown with "AttributeError: fixture has no attribute 'close'"`
- **THEN** the replay is not satisfied, and its report says that a fix needs a changed test that fails on base, or that errors there at collection or setup

#### Scenario: A comment does not change an errored file
- **WHEN** the head of a test file adds only a comment, and the file fails to collect on base
- **THEN** the command exits 1, and its report says that a test the fix does not change does not pass on the head and names the file

## MODIFIED Requirements

### Requirement: The replay reads no title, label or body
`devops ci fail-to-pass` SHALL take no pull request title, label or body. It SHALL fail unless at least one changed test fails on base, or errors there at collection or setup, or a case of a changed gate check fails on base and passes on head.

#### Scenario: An escape line in the environment
- **WHEN** `PR_TITLE` is `feat(ci): add a check`, `PR_BODY` holds `Fail-to-pass: not applicable: the tests pass on base`, and every changed test passes on base
- **THEN** `devops ci fail-to-pass --base main` exits 1 and prints no `not applicable` line

#### Scenario: The removed options
- **WHEN** `devops ci fail-to-pass` gets `--title`, `--labels` or `--body`
- **THEN** it exits 2 as for an unknown option

### Requirement: An unchanged test that still fails on the head refuses the replay
`devops ci fail-to-pass` SHALL treat a replay as not satisfied when an unchanged test fails or errors on base and does not pass on the head, or when it passes on the plain merge base. It SHALL NOT refuse the replay for an unchanged test that fails or errors on the plain merge base and passes on the head.

#### Scenario: An unchanged test fails
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base and does not pass on the head
- **THEN** the command exits 1, and its report says that a test the fix does not change does not pass on the head and names the unchanged test

#### Scenario: An unchanged test errors
- **WHEN** a changed test file holds one changed test that errors on base and one unchanged test that errors on base, passes on the plain merge base, and passes on the head
- **THEN** the command exits 1, and its report says that a test the fix does not change does not pass on the head and names the unchanged test

#### Scenario: An unchanged test that the head repairs
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base, fails on the plain merge base, and passes on the head
- **THEN** the command exits 0, and its report names the unchanged test as repaired on the head

#### Scenario: An unchanged test that passes on the plain merge base refuses the replay
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base, passes on the plain merge base, and passes on the head
- **THEN** the command exits 1, and its report says that a test the fix does not change fails on base and names the unchanged test

#### Scenario: A comment changes no test
- **WHEN** the head of a test only adds a comment or a blank line to a test that fails on base
- **THEN** the test counts as unchanged

#### Scenario: A changed helper changes every test
- **WHEN** the head of a changed test file changes a helper of that file, and a test that calls the helper and that the fix leaves alone fails on base
- **THEN** the replay is satisfied

### Requirement: The dry run lists the head replay
`devops ci fail-to-pass --dry-run` SHALL list the head replay of the test files that hold an unchanged failure with the condition `a test that failed or errored on base is unchanged`, and SHALL start no process.

#### Scenario: A dry run of the head replay
- **WHEN** `devops ci fail-to-pass --dry-run` runs
- **THEN** the plan lists the head pytest run with the condition `a test that failed or errored on base is unchanged`, and the process fake records no call
