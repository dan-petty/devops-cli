## ADDED Requirements

### Requirement: A shard test row has its own bound
The `test` row of a shard run SHALL stop at `DEFAULT_CI_TEST_SHARD_TIMEOUT_SECONDS` (900 s), and the unsharded row SHALL keep the default bound. The coverage-index build SHALL stop at `DEFAULT_CI_COVERAGE_INDEX_TIMEOUT_SECONDS` (3600 s).

#### Scenario: A shard test row
- **WHEN** the test row runs with `--shard 2 --shards 4`
- **THEN** its `timeout_seconds` is 900 s and its timeout line names the row

#### Scenario: The unsharded test row
- **WHEN** the test row runs with no shard
- **THEN** its `timeout_seconds` is None and the run takes the default bound

#### Scenario: The index build
- **WHEN** `devops ci coverage --build-index` starts the suite
- **THEN** the run takes `DEFAULT_CI_COVERAGE_INDEX_TIMEOUT_SECONDS` of 3600 s
