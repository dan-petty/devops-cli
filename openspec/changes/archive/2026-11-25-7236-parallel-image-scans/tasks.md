# Tasks

## 1. Behavior

- [x] 1.1 Give each category of the scan action its own Trivy cache directory
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.2 Run the three scans of the `Runner Image` job as background steps and wait for them
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.3 Keep the tests of the workflows green
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py`
