# Design

## Decisions
- Only a shard run writes the report and the skip summary. CI runs only shards, and #4250 reads the CI artifacts. A local unsharded run keeps its output as before.
- The report path is `.data/junit.xml`, relative to the checkout, beside the coverage `data_file` of `pyproject.toml`. Each shard runs on its own runner, so one fixed name does not collide. The download of the job `Tests & Coverage` puts each artifact in its own folder.
- The constants `CONST_CI_SHARD_JUNIT_PATH` and `CONST_CI_SHARD_SUMMARY_CHARS` hold the path and the summary characters. The test reads the path from the planned shard command and compares it with the upload step of `ci.yml`, so a change of one side fails the test.
- The report keeps the default `junit_duration_report = total`: the time of setup, call and teardown, which is the cost of the test for a shard split.
- The upload stays in the artifact `coverage-shard-<n>`, so the download pattern of the job `Tests & Coverage` does not change.

## Rejected alternatives
- `PYTEST_ADDOPTS`: `build_subprocess_env` refuses the key (#2747).
- `-rs` alone: it replaces the default `fE`, and the summary of a failed shard would not name the failed tests.
- `addopts` in `pyproject.toml`: each local run, each `devops ci test` and each mutation run would then write a report. Only the shards need it.
- A separate artifact for the report: it adds one upload and one name per shard for no gain, and the issue asks for the report in the coverage artifact.
