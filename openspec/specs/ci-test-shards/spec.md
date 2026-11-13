# ci-test-shards Specification

## Purpose
How `devops ci` runs one part of the test row, and how `ci.yml` splits the test job in shards and joins their coverage under the required name `Tests & Coverage`, so that the check stays under the five minute bound of AGENTS.md rule 5 while the suite grows.

## Requirements

### Requirement: The test row runs one shard of the suite
The command `devops ci` SHALL take the options `--shard <n>` and `--shards <total>`, whole numbers of at least 1 that default to 1. With `--shards` above 1, the command of the `test` row SHALL hold `--cov=src` and the paths of the test modules of shard `<n>`. It SHALL hold none of `--splits`, `--group` and `--splitting-algorithm`. With `--shards` at 1, the command SHALL be that of an unsharded run.

#### Scenario: Shard two of four
- **WHEN** the user runs `devops ci --dry-run --only test --shard 2 --shards 4`
- **THEN** the planned command holds the paths of the test modules of shard 2 and holds none of `--splits`, `--group` and `--splitting-algorithm`

#### Scenario: No shard
- **WHEN** the user runs `devops ci --dry-run --only test`
- **THEN** the planned command holds none of `--splits`, `--group` and `--cov-fail-under=0`, and holds `--cov-report=term-missing`

#### Scenario: A shard above the total
- **WHEN** the user runs `devops ci --only test --shard 5 --shards 4`
- **THEN** the command exits 2 and starts no check

### Requirement: A shard checks no floor and prints no report
The command of a shard SHALL hold `--cov-fail-under=0`, an empty `--cov-report=` and `--snapshot-warn-unused`, because a shard measures a part of the tree and the aggregate job checks the floor of the whole. The snapshots of the tests in the other shards are unused in a shard, and syrupy fails a run on unused snapshots.

#### Scenario: The shard command
- **WHEN** the command of shard 2 of 4 is built
- **THEN** it holds `--cov-fail-under=0`, `--cov-report=` and `--snapshot-warn-unused`, and holds no `--cov-report=term-missing`

### Requirement: A sharded run reads and writes no cached verdict
A run of `devops ci` with `--shards` above 1 SHALL be a narrowed run: it SHALL NOT take a cached verdict as proof and SHALL NOT record its result as one.

#### Scenario: A shard passes
- **WHEN** a run with `--shards 4` passes
- **THEN** no entry of the gate cache is written for the tree

### Requirement: The workflow runs the test row in shards
The workflow `ci.yml` SHALL run the job `test-shard` as a matrix over the shards, with names of the form `Tests & Coverage (shard <n> of <total>)`. Each shard SHALL run `uv run devops ci --check --no-cache --only test --shard <n> --shards <total>` and SHALL upload `.data/.coverage` as an artifact.

#### Scenario: The shard job is read
- **WHEN** the job `test-shard` of `ci.yml` is read
- **THEN** it has a matrix of shards, a name of the form above and a gate step that passes its shard and the total to `devops ci`

### Requirement: The job Tests & Coverage aggregates the shards
The job `test`, named `Tests & Coverage`, SHALL wait for the shards, SHALL run when no job was cancelled, and SHALL fail when a shard did not succeed. It SHALL combine the downloaded data with `coverage combine` and run `coverage report`, which applies `fail_under` of `pyproject.toml`. The names `Static Analysis`, `Tests & Coverage` and `Semantic PR title` SHALL stay the names of the required checks.

#### Scenario: The aggregate job is read
- **WHEN** the job `test` of `ci.yml` is read
- **THEN** it has the name `Tests & Coverage`, needs `test-shard`, and no other job needs it

#### Scenario: A shard fails
- **WHEN** one shard ends with a failure
- **THEN** the job `Tests & Coverage` runs and ends with a failure, and does not end skipped

#### Scenario: Coverage under the floor
- **WHEN** the combined data covers less than `fail_under`
- **THEN** the step that runs `coverage report` fails

### Requirement: A plan-only pull request runs the invariant tests in one shard
When a pull request only adds files of active change folders, shard 1 SHALL run `uv run devops ci test tests/invariants`, no shard SHALL run the gate step or upload coverage data, and the job `Tests & Coverage` SHALL run no download and no coverage step, so that the required check reports success.

#### Scenario: A plan-only pull request
- **WHEN** the filter step reports `outside_plan` as `false`
- **THEN** only shard 1 runs the invariant tests, and the aggregate job skips its checkout, download, combine and changed-line coverage steps

### Requirement: The implement watch reads the log of a failed shard
When the join check `Tests & Coverage` and a shard check `Tests & Coverage (shard n of N)` both fail, the roadmap implement watch SHALL name the shard check as the failed check, because the log of the join check holds no test output.

#### Scenario: A shard and the join fail
- **WHEN** the join check and one shard check are failed checks of the pull request
- **THEN** the watch reports the shard check, and the fix step reads the log of that shard

### Requirement: Each shard collects only its own test files
The shards SHALL partition the test modules of `tests/`: each module SHALL be in exactly one shard, and no shard SHALL be empty. The split SHALL be the same in every call. It SHALL be computed from the files of the checkout alone: the test modules and the record `tests/module_durations.json`.

#### Scenario: Four shards cover every test module once
- **WHEN** the module lists of shards 1 to 4 of 4 are built for the tree
- **THEN** every test module of `tests/` is in exactly one list, and no list is empty

#### Scenario: The split is the same in every call
- **WHEN** the module list of a shard is built twice, in any order of the shards
- **THEN** the two lists are equal

#### Scenario: The split has no stored input
- **WHEN** the modules of a tree without `tests/module_durations.json` are dealt to two shards
- **THEN** the lists come from the line counts of the files, the heaviest file going first to the shard with the fewest lines so far

### Requirement: A shard reports the time of each test and the reason of each skip
The command of a shard SHALL hold `-rfEs` and `--junitxml=.data/junit.xml`, so that its log gives the reason of each skip and still names the failed and error tests, and the report holds each test of the shard with its time. The job `test-shard` of `ci.yml` SHALL upload the report in the artifact that holds `.data/.coverage`.

#### Scenario: A shard runs a pass, a skip and a failure
- **WHEN** the report options of the command of shard 2 of 4 run on a suite with one pass, one skip and one failure
- **THEN** the report holds the three tests, and the summary gives the reason of the skip and names the failed test

#### Scenario: The upload step is read
- **WHEN** the upload step of the job `test-shard` of `ci.yml` is read
- **THEN** its paths are the `data_file` of `[tool.coverage.run]` in `pyproject.toml` and the report path of the shard command

### Requirement: The shards balance the recorded seconds
The split SHALL weigh each test module by its seconds in `tests/module_durations.json`. A module that the record does not hold SHALL weigh its lines times the recorded seconds per line of the recorded modules of the tree. A recorded module that the tree does not hold SHALL be in no shard and SHALL NOT count in that rate. The modules SHALL go, heaviest first and then by path, to the shard with the least weight so far, and a tie SHALL go to the lower shard.

#### Scenario: A short module with a long recorded time
- **WHEN** a module of 10 lines has a record of 300 seconds and three modules of 500 lines each have 10 seconds, and the modules are dealt to two shards
- **THEN** the short module is alone in its shard and the three other modules share the other shard

#### Scenario: A module without a record
- **WHEN** two recorded modules of 100 lines each have 100 and 10 seconds, a third module of 100 lines has no record, and the modules are dealt to two shards
- **THEN** the third module weighs 55 seconds and shares a shard with the module of 10 seconds

#### Scenario: A deleted module in the record
- **WHEN** the record holds a module that the tree does not hold
- **THEN** no shard holds it, and its seconds do not change the weight of a module without a record

### Requirement: The record is written from the shard reports of CI
`devops ci durations` SHALL read the last 20 push runs of `ci.yml` on `main` where `Tests & Coverage` ran to an end. It SHALL download their `coverage-shard-*` artifacts with `gh run download` and read the time of each test from the JUnit XML reports. It SHALL write the mean seconds of each module of the tree over the runs that ran it to `tests/module_durations.json`, in tenths of a second.

#### Scenario: Two runs with reports and one without
- **WHEN** run 2 holds two shard reports, run 1 one report, and run 3 only an expired shard artifact, and the user runs `devops ci durations --runs 3`
- **THEN** gh downloads the artifacts of runs 2 and 1 only, and the record holds the mean of each module over the runs that ran it

### Requirement: No record without a report
When no run read holds a shard artifact that GitHub still keeps, `devops ci durations` SHALL exit 1 and write no record. A dry run SHALL list its requests and the download, and make none.

#### Scenario: No run holds a report
- **WHEN** the shard artifacts of every run read are expired
- **THEN** the command exits 1, writes no record and downloads nothing

#### Scenario: Dry run
- **WHEN** the user runs `devops ci durations --dry-run`
- **THEN** the plan names the listing of runs, the jobs and artifacts of each run and the download, and no request is made
