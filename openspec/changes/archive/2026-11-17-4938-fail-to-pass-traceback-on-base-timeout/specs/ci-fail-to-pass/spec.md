## MODIFIED Requirements

### Requirement: A replay that cannot run names the next step

When the replay's pytest is interrupted, stops with an internal or usage error, passes the
process-runner limit, or writes no complete JUnit report, the check SHALL fail, and its report
SHALL tell the author to merge the change to the test harness or the dependencies first, in a pull
request that is not a fix.

#### Scenario: pytest stops with an internal error

- **WHEN** the replay's pytest exits with status 3 and writes no JUnit report
- **THEN** the command exits 1, and its report says that the replay could not run and to merge the change to the test harness or to the dependencies first, in a pull request that is not a fix

### Requirement: A head replay that cannot run refuses the replay

`devops ci fail-to-pass` SHALL treat a replay as not satisfied when the head replay of the test
files that hold an unchanged failure is interrupted, stops with an internal or usage error, passes
the process-runner limit, or writes no complete JUnit report. Its report SHALL name the head run
and pytest's exit status, or the limit when pytest passed it.

#### Scenario: A head replay that writes no complete report

- **WHEN** the head replay of the test files that hold an unchanged failure writes no complete JUnit report
- **THEN** the command exits 1, and its report says that the replay could not run on the head and names pytest's exit status

#### Scenario: A head replay that passes the process-runner limit

- **WHEN** the head replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`
- **THEN** the command exits 1, and its report names the limit and the test files and prints no pytest exit status

## ADDED Requirements

### Requirement: A replay that passes the process-runner limit names the limit

When a replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`, the report SHALL name the limit and
each test file of the replay, and SHALL NOT print a pytest exit status that pytest did not return.
The base, plain-base, head and gate-row replays SHALL use this report.

#### Scenario: The base replay passes the limit

- **WHEN** the base replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`
- **THEN** the command exits 1, the report names the limit and the test files, and it prints no traceback or pytest exit status

#### Scenario: A gate row passes the limit

- **WHEN** a gate-row replay stops after `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS`
- **THEN** the report names the row, the tree and the limit, and prints no pytest exit status
