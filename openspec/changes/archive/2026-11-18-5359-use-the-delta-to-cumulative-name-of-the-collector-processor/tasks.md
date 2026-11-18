# Tasks

## 1. Behavior

- [x] 1.1 Rename the processor key and its metrics pipeline entry to `delta_to_cumulative` in `k8s/otel/values.yaml`
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Follow the rename in the dashboard, the code comments and the tests
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py`

## 2. Documents

- [x] 2.1 Follow the rename in the telemetry document, its generator and `k8s/README.md`
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 2.2 Extend the `command-telemetry` and `monitoring-collectors` capabilities
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: render the chart and run `validate --config` of `otel/opentelemetry-collector-contrib:0.163.2` on the rendered configuration, then start the same image and read the start log.
- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
