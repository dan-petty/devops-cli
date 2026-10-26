# Tasks

## 1. Failing tests

- [x] Add the tests that fail on `main`: the item counts of the board, the milestone filter, a failed board read, the labels on the wire, the 0 for a label set that left, the panel queries, and the Service job that counts the items of its own store
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_telemetry_instruments.py tests/test_roadmap_run.py`
- [x] Move the `captured` fixture to `tests/support/telemetry_capture.py` so that both metrics test modules share one double of the OTLP edge
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py`

## 2. Item counts

- [x] Add `PROJECT_ITEM_LABELS` to `src/devops_cli/telemetry/instruments.py` and write the description of `PROJECT_ITEMS` with the labels
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] Add `ItemCountMetric`, `get_item_metrics` and the `store` argument of `collect_project_metrics_report` to `src/devops_cli/github/metrics.py`, and pass the store of the job from `_run_metrics_adapter` in `src/devops_cli/roadmap/run.py`
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_roadmap_run.py`
- [x] Send the item counts and the 0 for each label set that left, record them in the in-memory registry, and delete the loops that sent the REST milestone counts; register `reset_sent_item_series` in `tests/conftest.py`
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_architectural_invariants.py`

## 3. Dashboard and documentation

- [x] Change the two panels of `k8s/monitoring/dashboards/project-metrics.json`: the descriptions, and `none` for an item in no milestone
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] Regenerate the documentation with `devops docs generate --sync-readme`
  - Verification: `uv run devops ci test tests/test_docs.py`

## 4. Verification and static checks

- [x] Verify the fail-to-pass check run against `origin/main`
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify that the full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- #2288: the double count of a gauge that reaches Prometheus through the scrape of the Service pod and through OTLP.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
