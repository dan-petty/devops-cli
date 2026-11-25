# Tasks

## 1. Command hints and option context (kind: behavior)

- [x] 1.1 Write failing tests for YAML hints, cross-group lookup, `ci list`/`ci --list`, option filtering/`<=6` expansion, missing-option help, hint target resolution, difflib non-duplication, and `hinted` telemetry
  - Verification: `$ uv run devops ci test tests/telemetry/test_usage_errors.py tests/core/test_usage_hints.py`
- [x] 1.2 Implement `src/devops_cli/core/usage_hints.yaml`, `src/devops_cli/core/usage_hints.py`, extract `CONST_CI_CHECK_ROW_NAMES` to `src/devops_cli/config/constants.py` (aliased as `CHECK_ROW_NAMES` in `src/devops_cli/commands/ci.py`), hook into `src/devops_cli/core/cli.py`, and add `hinted` field to `UsageErrorRecord` in `src/devops_cli/telemetry/usage_errors.py`
  - Verification: `$ uv run devops ci test tests/telemetry/test_usage_errors.py tests/core/test_usage_hints.py`

## 2. Telemetry docs (kind: documents)

- [x] 2.1 Update `src/devops_cli/docs/generator.py` to document `hinted` (`usage.hinted`) and regenerate `docs/TELEMETRY.md`
  - Verification: `$ uv run devops ci docs`

## 3. Quality gate

- [x] 3.1 Pass full local CI gate and OpenSpec checks
  - Verification: `$ uv run devops ci --check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
