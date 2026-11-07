# Tasks

## 1. Sweep

Reads: `src/devops_cli/research/advisories.py`, `src/devops_cli/review/handoff.py`, `src/devops_cli/commands/research.py`. Changes: `src/devops_cli/research/sweep.py`, `src/devops_cli/research/models.py`, `src/devops_cli/commands/research.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/`, `tests/research/test_sweep.py`, `tests/research/osv_recording.py`.

- [x] 1.1 Add the tests of the first sweep, the second sweep, the non-actionable finding, the plan, the skipped candidate, the public body, the secret refusal, the gauge and the command with its dry run
  - Verification: `uv run devops ci test tests/research/test_sweep.py`
- [x] 1.2 Add the report models, `sweep.py`, the gauge and the command `devops research sweep`
  - Verification: `uv run devops ci test tests/research tests/telemetry/test_telemetry_instruments.py`

## 2. Alert rule

Reads: `k8s/monitoring/prometheus-values.yaml`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/research_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [x] 2.1 Add the promtool unit tests and the rule group `research` with the rule `ResearchCriticalFindings`
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 3. Documentation

Reads: `docs/TELEMETRY.md`, `k8s/README.md`. Changes: `docs/TELEMETRY.md`, `k8s/README.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/research.md`.

- [x] 3.1 Add the telemetry row and the alert row, and regenerate the command pages
  - Verification: `uv run devops docs generate --check`

## Workflow follow-up

- Not in this change: the exploited condition (CISA KEV) and the end-of-life condition. Issue #3987 holds the first and issue #3907 holds the second.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
