# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the shard row writes each test to a JUnit XML report, gives the reason of each skip and keeps the failure summary, and the shard job uploads that report with its coverage data
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py`
- [x] 1.2 Add `-rfEs` and `--junitxml=.data/junit.xml` to the shard row, and upload the report in the artifact of each shard
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py`

## 2. Workflows

- [x] 2.1 Lint the changed workflow
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 3. Documents

- [x] 3.1 Say in docs/SDLC.md that each shard uploads its JUnit XML report and gives the reason of each skip
  - Verification: `$ uv run devops ci docs`
