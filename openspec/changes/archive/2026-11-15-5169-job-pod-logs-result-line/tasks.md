# Tasks

## 1. Behavior

- [x] 1.1 Write acceptance tests for job result line export and non-result INFO filtering
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_logging_bridge.py`
- [x] 1.2 Set INFO level on job_result logger and configure OTelLoggingHandler to export job_result at INFO
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_logging_bridge.py`

## 2. Documents

- [x] 2.1 Update documentation and spec requirements
  - Verification: `$ uv run devops ci docs`
