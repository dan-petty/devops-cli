# ci-test-shards Specification

## Purpose
How `devops ci` runs one part of the test row, and how `ci.yml` splits the test job in shards and joins their coverage under the required name `Tests & Coverage`, so that the check stays under the five minute bound of AGENTS.md rule 5 while the suite grows.

## Requirements

### Requirement: The test row runs one shard of the suite
The command `devops ci` SHALL take the options `--shard <n>` and `--shards <total>`, whole numbers of at least 1 that default to 1. With `--shards` above 1, the command of the `test` row SHALL hold `--splits <total>`, `--group <n>`, `--splitting-algorithm least_duration` and `--cov=src`. With `--shards` at 1, the command SHALL be that of an unsharded run.

#### Scenario: Shard two of four
- **WHEN** the user runs `devops ci --dry-run --only test --shard 2 --shards 4`
- **THEN** the planned command holds `--splits 4`, `--group 2` and `--splitting-algorithm least_duration`

#### Scenario: No shard
- **WHEN** the user runs `devops ci --dry-run --only test`
- **THEN** the planned command holds none of `--splits`, `--group` and `--cov-fail-under=0`, and holds `--cov-report=term-missing`

#### Scenario: A shard above the total
- **WHEN** the user runs `devops ci --only test --shard 5 --shards 4`
- **THEN** the command exits 2 and starts no check

### Requirement: A shard checks no floor and prints no report
The command of a shard SHALL hold `--cov-fail-under=0` and an empty `--cov-report=`, because a shard measures a part of the tree and the aggregate job checks the floor of the whole.

#### Scenario: The shard command
- **WHEN** the command of shard 2 of 4 is built
- **THEN** it holds `--cov-fail-under=0` and `--cov-report=`, and holds no `--cov-report=term-missing`

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
