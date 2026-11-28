## MODIFIED Requirements

### Requirement: The test row runs one shard of the suite
The command `devops ci` SHALL take the options `--shard <n>` and `--shards <total>`, whole numbers of at least 1 that default to 1. With `--shards` above 1, the command of the `test` row SHALL hold `--cov=src`, `--splits <total>`, `--group <n>` and `--splitting-algorithm least_duration`, so that pytest-split runs group `<n>` of the suite. It SHALL hold no path of a test module. With `--shards` at 1, the command SHALL be that of an unsharded run.

#### Scenario: Shard two of four
- **WHEN** the user runs `devops ci --dry-run --only test --shard 2 --shards 4`
- **THEN** the planned command holds `--splits 4 --group 2 --splitting-algorithm least_duration` and no path under `tests/`

#### Scenario: No shard
- **WHEN** the user runs `devops ci --dry-run --only test`
- **THEN** the planned command holds none of `--splits`, `--group` and `--cov-fail-under=0`, and holds `--cov-report=term-missing`

#### Scenario: A shard above the total
- **WHEN** the user runs `devops ci --only test --shard 5 --shards 4`
- **THEN** the command exits 2 and starts no check

## ADDED Requirements

### Requirement: pytest-split gives each test to exactly one shard
The split options of the shard rows SHALL make pytest-split select each collected test in exactly one shard. With no `.test_durations` in the tree, each test SHALL weigh the same, and the shards SHALL take the tests in turn.

#### Scenario: Six tests and two shards
- **WHEN** the split options of the rows of shards 1 and 2 of 2 run with pytest-split on six tests, in a tree with no `.test_durations`
- **THEN** shard 1 selects the first, third and fifth tests, and shard 2 selects the second, fourth and sixth tests

### Requirement: A shard gives the reason of each skip
The command of a shard SHALL hold `-rfEs`, so that its log gives the reason of each skip and still names the failed and error tests. It SHALL write no JUnit XML report. The job `test-shard` of `ci.yml` SHALL upload `.data/.coverage` as the artifact of the shard.

#### Scenario: A shard runs a pass, a skip and a failure
- **WHEN** the report options of the command of shard 2 of 4 run on a suite with one pass, one skip and one failure
- **THEN** the summary gives the reason of the skip and names the failed test, and the command holds no `--junitxml`

#### Scenario: The upload step is read
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` checks `ci.yml`
- **THEN** the check passes, and the upload step of the job `test-shard` names only `.data/.coverage`

## REMOVED Requirements

### Requirement: Each shard collects only its own test files
**Reason**: pytest-split selects the tests of a shard after collection, so a shard collects the whole suite (#7500).
**Migration**: None. The split options of the shard row replace the list of test files.

### Requirement: A shard reports the time of each test and the reason of each skip
**Reason**: Only `devops ci durations` read the JUnit XML report of a shard, and that command is removed (#7500).
**Migration**: The requirement "A shard gives the reason of each skip" keeps the summary of the skips.

### Requirement: The shards balance the recorded seconds
**Reason**: The `least_duration` algorithm of pytest-split splits the tests, and the repository holds no record of their times (#7500).
**Migration**: None. `tests/module_durations.json` is deleted.

### Requirement: The record is written from the shard reports of CI
**Reason**: `devops ci durations` is removed, and the split reads no record (#7500).
**Migration**: None.

### Requirement: No record without a report
**Reason**: `devops ci durations` is removed (#7500).
**Migration**: None.
