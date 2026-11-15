# Tasks

## 1. Trace the group body

Reads: `src/devops_cli/core/cli.py`, `tests/telemetry/test_telemetry.py`.

Changes: `src/devops_cli/core/cli.py`, `tests/telemetry/test_telemetry.py`.

- [x] 1.1 Write the histogram test of a group body, and watch it fail.
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py`
- [x] 1.2 Trace the callback when no sub-command runs, and leave a sub-command run alone.
  - Verification: `$ uv run devops ci test tests/telemetry`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
