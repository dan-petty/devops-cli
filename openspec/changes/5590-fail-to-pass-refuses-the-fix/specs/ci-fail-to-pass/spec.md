## ADDED Requirements

### Requirement: The report names a repaired test
`devops ci fail-to-pass` SHALL name in its report each test that the fix does not change, that fails on base and that passes on the head, as repaired on the head.

#### Scenario: A repaired test in the report
- **WHEN** an unchanged test fails on base and passes on the head
- **THEN** the report holds a line that names the test and says that the head repairs it

### Requirement: A head replay that cannot run refuses the replay
`devops ci fail-to-pass` SHALL treat a replay as not satisfied when the head replay of the test files that hold an unchanged failure is interrupted, stops with an internal or usage error, or writes no complete JUnit report, and its report SHALL name the head run and pytest's exit status.

#### Scenario: A head replay that writes no complete report
- **WHEN** the head replay of the test files that hold an unchanged failure writes no complete JUnit report
- **THEN** the command exits 1, and its report says that the replay could not run on the head and names pytest's exit status

### Requirement: The dry run lists the head replay
`devops ci fail-to-pass --dry-run` SHALL list the head replay of the test files that hold an unchanged failure with the condition `a test that failed on base is unchanged`, and SHALL start no process.

#### Scenario: A dry run of the head replay
- **WHEN** `devops ci fail-to-pass --dry-run` runs
- **THEN** the plan lists the head pytest run with the condition `a test that failed on base is unchanged`, and the process fake records no call

## MODIFIED Requirements

### Requirement: An unchanged test that still fails on the head refuses the replay
`devops ci fail-to-pass` SHALL treat a replay as not satisfied when a test that the fix does not change fails on base and does not pass on the head, and its report SHALL name that test. It SHALL NOT refuse the replay for such a test when the head passes it.

#### Scenario: An unchanged test that still fails on the head
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base and does not pass on the head
- **THEN** the command exits 1, and its report says that a test the fix does not change does not pass on the head and names the unchanged test

#### Scenario: An unchanged test that the head repairs
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that fails on base and passes on the head
- **THEN** the command exits 0, and its report names the unchanged test as repaired on the head

#### Scenario: A comment changes no test
- **WHEN** the head of a test only adds a comment or a blank line to a test that fails on base
- **THEN** the test counts as unchanged

#### Scenario: A changed helper changes every test
- **WHEN** the head of a changed test file changes a helper of that file, and a test that calls the helper and that the fix leaves alone fails on base
- **THEN** the replay is satisfied

#### Scenario: An unchanged test fails
- **WHEN** a changed test file holds one changed test that fails on base and one unchanged test that also fails on base
- **THEN** the command exits 1, and its report says that a test the fix does not change fails on base and names the unchanged test

### Requirement: The head run of a named head uses a worktree of that head
For `--head HEAD`, `devops ci fail-to-pass` SHALL run the head row and the head replay of the unchanged failures in the working tree, so a change that is not committed counts. For another head, it SHALL run both in one detached worktree of that head, and remove that worktree after the runs.

#### Scenario: A named head
- **WHEN** the command runs with `--head feature` for a fix that changes a gate check
- **THEN** it adds one detached worktree of `feature`, runs the head row there, and removes the worktree

#### Scenario: A named head with an unchanged failure
- **WHEN** the command runs with `--head feature` for a fix whose base replay holds an unchanged failure
- **THEN** it runs the head replay of those test files in the same worktree

#### Scenario: The default head
- **WHEN** the command runs with the default `--head HEAD` and the base replay holds an unchanged failure
- **THEN** it runs the head replay in the working tree and adds no worktree

## RENAMED Requirements

- FROM: `### Requirement: A failed test that the fix does not change refuses the replay`
- TO: `### Requirement: An unchanged test that still fails on the head refuses the replay`
