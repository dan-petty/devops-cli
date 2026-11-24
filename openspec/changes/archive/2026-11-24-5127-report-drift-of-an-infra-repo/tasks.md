# Tasks

## 1. Behavior

- [x] 1.1 Register telemetry instrument `devops_cli_infra_drift_hosts` and extend `devops_cli_infra_runs_total`
  - Verification: `$ uv run devops ci test tests/test_telemetry.py`
- [x] 1.2 Implement GitHub issue lifecycle helper and `devops infra drift` core logic in `src/devops_cli/infra/drift.py`
  - Verification: `$ uv run devops ci test tests/infra/test_drift.py`
- [x] 1.3 Add CLI command `devops infra drift` in `src/devops_cli/commands/infra.py` and register help and error texts
  - Verification: `$ uv run devops ci test tests/commands/test_infra_drift.py`
- [x] 1.4 Add unit and integration tests covering exit codes, marker issues, plan comparisons, metrics, and dry-run
  - Verification: `$ uv run devops ci test tests/commands/test_infra_drift.py tests/infra/test_drift.py`

## 2. Documents

- [x] 2.1 Update telemetry documentation in `docs/TELEMETRY.md` and CLI documentation
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Run live drift check on `dan-petty/homelab` and record results
  - Verification: `$ uv run devops infra drift dan-petty/homelab`
