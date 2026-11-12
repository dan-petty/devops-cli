## ADDED Requirements

### Requirement: A shard reports the time of each test and the reason of each skip
The command of a shard SHALL hold `-rfEs` and `--junitxml=.data/junit.xml`, so that its log gives the reason of each skip and still names the failed and error tests, and the report holds each test of the shard with its time. The job `test-shard` of `ci.yml` SHALL upload the report in the artifact that holds `.data/.coverage`.

#### Scenario: A shard runs a pass, a skip and a failure
- **WHEN** the report options of the command of shard 2 of 4 run on a suite with one pass, one skip and one failure
- **THEN** the report holds the three tests, and the summary gives the reason of the skip and names the failed test

#### Scenario: The upload step is read
- **WHEN** the upload step of the job `test-shard` of `ci.yml` is read
- **THEN** its paths are the `data_file` of `[tool.coverage.run]` in `pyproject.toml` and the report path of the shard command
