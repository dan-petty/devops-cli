# Tasks

## 1. Renovate proposes each Grafana plugin release

- [x] Add failing tests: a custom manager reads each plugin pin and nothing else, its datasource reads grafana.com, and the plugin rule holds each update below the next major in its own pull request with the compatibility note
  - Verification: `uv run devops ci test tests/test_renovate_config.py`
- [x] Add the custom datasource, the regex manager and the package rule to `.github/renovate.json`
  - Verification: `uv run devops ci test tests/test_renovate_config.py tests/test_k8s_monitoring_integration.py`
- [x] Describe the manager in `docs/SDLC.md` and in the comment above the pins
  - Verification: `uv run devops docs check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2054-grafana-plugin-renovate`
- Pending a person: after the merge, check that the Renovate App's next run reports no configuration error and opens one pull request for each plugin with a newer 3.x release.
- Pending a person: before merging a plugin pull request, check the release's `grafanaDependency` against the Grafana image of the `grafana` chart.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
