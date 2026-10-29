# Tasks

## 1. Items by release

- [x] Change the tests to count the Items by release, map each issue to the first tag whose commits close it, and read the panel "Items by Release"
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_telemetry_instruments.py tests/test_roadmap_run.py`
- [x] Add `get_item_releases` and the `release` label of `ItemCountMetric` to `src/devops_cli/github/metrics.py`, and replace `milestone` with `release` in `PROJECT_ITEM_LABELS` and the description of `PROJECT_ITEMS`
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_roadmap_run.py`
- [x] Change the row and the panel of `k8s/monitoring/dashboards/project-metrics.json` to the release, and the gauge row of `docs/TELEMETRY.md`; regenerate the documentation with `devops docs generate --sync-readme`
  - Verification: `uv run devops ci test tests/test_telemetry_instruments.py tests/test_docs.py`

## 2. Verification and static checks

- [x] Verify the fail-to-pass check run against `origin/main`
  - Verification: `uv run devops ci fail-to-pass --base origin/main`

## Workflow follow-up

- Pending a person: check the panel "Items by Release" on the live dashboard after the next metrics snapshot.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
