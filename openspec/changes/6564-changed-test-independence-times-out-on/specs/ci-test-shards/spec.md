## ADDED Requirements

### Requirement: The test command runs one shard of the files it selects
The command `devops ci test` SHALL take the options `--shard <n>` and `--shards <total>`, whole numbers of at least 1 that default to 1. With `--shards` above 1, the run SHALL pass to pytest only the files of shard `<n>` of the files that it selects, weighed by the recorded seconds of each test module. A run whose shard holds no file SHALL exit 0 and SHALL start no pytest.

#### Scenario: Three shards of a changed-file list
- **WHEN** a test runs `devops ci test --shard 2 --shards 3` on a list of changed test files
- **THEN** the run passes only the files of shard 2 to pytest, and the three shard lists together hold each file of the list exactly once

#### Scenario: A shard above the total
- **WHEN** the user runs `devops ci test --shard 5 --shards 4`
- **THEN** the command exits 2 and starts no pytest

#### Scenario: A shard with no file
- **WHEN** a test runs `devops ci test --shard 8 --shards 8` on a list of one changed test file
- **THEN** the run exits 0 and starts no pytest

### Requirement: Each repeat pass of a shard runs the files of that shard
A run of `devops ci test` with `--repeat` above 0 and `--shards` above 1 SHALL run each of its passes over the files of its own shard only, with the seeds that `--seed` gives.

#### Scenario: Three shuffled passes of shard 1
- **WHEN** a test runs `devops ci test --repeat 3 --shard 1 --shards 2` on a list of changed test files
- **THEN** each of the three passes gets every file of shard 1 and no file of shard 2

### Requirement: The workflow runs Changed-Test Independence in shards
The workflow `.github/workflows/ci.yml` SHALL run the job `changed-tests` as a matrix over eight shards named `Changed-Test Independence (shard <n> of <total>)`, and each shard SHALL pass `--repeat 3`, `--shard <n>` and `--shards <total>` to `devops ci test` over the changed test files. One job named `Changed-Test Independence` SHALL need the matrix and SHALL fail when the matrix does not succeed.

#### Scenario: The workflow gates on the edited file
- **WHEN** a contributor runs `uv run devops ci --check --only actionlint,zizmor` on `.github/workflows/ci.yml`
- **THEN** the command exits 0 and reports no finding

#### Scenario: One failing shard
- **WHEN** one shard job of `changed-tests` fails on a pull request
- **THEN** the job `Changed-Test Independence` ends red, and `uv run devops ci --check --only actionlint,zizmor` exits 0 on `.github/workflows/ci.yml`
