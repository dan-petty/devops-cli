## ADDED Requirements

### Requirement: A behavior group's tests fail on the base commit

The implement step SHALL replay the test files of a behavior group on the base commit of the group, with the tests of the head overlaid. The step SHALL accept the group only when one test of those files fails in its call phase on the base commit.

#### Scenario: Tests pass on base

- **WHEN** every test of the test files of a behavior group passes on the base commit
- **THEN** the step stops with a message that names the test files, and it gets one repair round that may change only test files.

#### Scenario: Tests error on base

- **WHEN** a test file of a behavior group cannot be collected on the base commit, and no test of the group fails there
- **THEN** the step stops with a message, and the collection error does not count as a failure on the base commit.

#### Scenario: A test fails on base

- **WHEN** a test of a behavior group fails in its call phase on the base commit and passes after the change
- **THEN** the step continues with the other exit checks.

#### Scenario: No test file changed

- **WHEN** a behavior group changes no test file
- **THEN** the step stops with a message and gets no repair round.

### Requirement: The trace holds each base replay

The implement step SHALL add one check event to the trace for each replay of a behavior group on the base commit. The event SHALL hold the exit status of the replay.

#### Scenario: A replay is a check event

- **WHEN** the step replays the tests of a behavior group on the base commit
- **THEN** the trace holds one check event for the replay, with its exit status.

### Requirement: The PR comment shows the fail-to-pass result of each behavior group

The PR comment of a step SHALL show one line for each behavior group that passed the exit checks. The line SHALL name the group, the result on the base commit and the tests that failed there.

#### Scenario: A behavior group passed

- **WHEN** a behavior group passes the exit checks after a test failed on the base commit
- **THEN** the PR comment holds one line that names the group, the result of the replay and the failed test.

### Requirement: A group of kind other records its verify output

The implement step SHALL keep the output of each verification command of a group of kind `other` that passes. The PR comment SHALL show each command with its exit status and its masked, bounded output.

#### Scenario: A verify command of an other group prints a line

- **WHEN** a group of kind `other` passes its verify command, and the command prints one line
- **THEN** the step outcome holds that command, its exit status and that line.
